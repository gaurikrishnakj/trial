# client.py (Final Architecture - Solves Race Condition)
import cv2
import mediapipe as mp
import numpy as np
import asyncio
import logging
import argparse
import json
from aiohttp import ClientSession

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaStreamTrack
from av import VideoFrame

# Configure logging
logging.basicConfig(level=logging.INFO)

# --- U-LANC Video Processing Logic ---
mp_selfie_segmentation = mp.solutions.selfie_segmentation
segmentation = mp_selfie_segmentation.SelfieSegmentation(model_selection=0)
received_frames = {}

class QueuedVideoStreamTrack(MediaStreamTrack):
    """
    A video track that reads frames from an asyncio.Queue.
    """
    kind = "video"
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    async def recv(self):
        # Get the next frame from the queue
        frame = await self.queue.get()
        return frame

async def video_processor(camera_track, face_queue, background_queue, shared_state):
    """
    A central coroutine that reads from the camera, runs segmentation ONCE,
    and puts the processed frames into their respective queues.
    """
    while True:
        frame = await camera_track.recv()
        img = frame.to_ndarray(format="bgr24")

        # --- Run expensive AI model only ONCE per frame ---
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = segmentation.process(rgb_img)
        condition = np.stack((results.segmentation_mask,) * 3, axis=-1) > 0.1

        # --- Create the Face Frame ---
        green_screen = np.zeros_like(img)
        green_screen[:] = (0, 255, 0) # BGR for green
        face_img = np.where(condition, img, green_screen)
        face_frame = VideoFrame.from_ndarray(face_img, format="bgr24")
        face_frame.pts, face_frame.time_base = frame.pts, frame.time_base
        
        # --- Create the Background Frame based on network quality ---
        if shared_state["quality"] == "high":
            black_silhoutte = np.zeros_like(img)
            background_img = np.where(condition, black_silhoutte, img)
        else: # low quality
            background_img = cv2.GaussianBlur(img, (99, 99), 0)
        
        background_frame = VideoFrame.from_ndarray(background_img, format="bgr24")
        background_frame.pts, background_frame.time_base = frame.pts, frame.time_base

        # --- Push frames to their queues for sending ---
        if not face_queue.full():
            await face_queue.put(face_frame)
        if not background_queue.full():
            await background_queue.put(background_frame)

async def monitor_network(pc, shared_state):
    """
    Monitors network stats and updates the shared state.
    """
    while True:
        await asyncio.sleep(5)
        try:
            stats = await pc.getStats()
            for report in stats.values():
                if report["type"] == "candidate-pair" and report.get("state") == "succeeded":
                    available_bitrate = report.get("availableOutgoingBitrate")
                    if available_bitrate:
                        if available_bitrate > 800_000:
                            if shared_state["quality"] != "high":
                                logging.info("Network is GOOD. Sending clear background.")
                                shared_state["quality"] = "high"
                        else:
                            if shared_state["quality"] != "low":
                                logging.info("Network is POOR. Sending lossy (blurred) background.")
                                shared_state["quality"] = "low"
        except Exception as e:
            logging.error(f"Error getting stats: {e}")

async def run(pc, role, signaling_server):
    session = ClientSession()

    @pc.on("track")
    def on_track(track):
        logging.info(f"Track {track.kind} received, id={track.id}")
        received_frames[track.id] = None
        @track.on("ended")
        async def on_ended():
            logging.info(f"Track {track.id} ended")
            if track.id in received_frames: del received_frames[track.id]
        async def process_track():
            while True:
                try:
                    frame = await track.recv()
                    received_frames[track.id] = frame.to_ndarray(format="bgr24")
                except Exception:
                    if track.id in received_frames: del received_frames[track.id]
                    break
        asyncio.ensure_future(process_track())

    if role == "send":
        from aiortc.contrib.media import MediaPlayer
        player = MediaPlayer("video=Integrated Camera", format="dshow", options={"video_size": "640x480"})

        # Create queues and shared state
        shared_state = {"quality": "high"}
        face_queue = asyncio.Queue(maxsize=1)
        background_queue = asyncio.Queue(maxsize=1)
        
        # Create tracks that read from queues
        face_track = QueuedVideoStreamTrack(face_queue)
        background_track = QueuedVideoStreamTrack(background_queue)
        pc.addTrack(face_track)
        pc.addTrack(background_track)

        # Start the central processor and network monitor
        asyncio.ensure_future(video_processor(player.video, face_queue, background_queue, shared_state))
        asyncio.ensure_future(monitor_network(pc, shared_state))

        # Standard signaling
        await pc.setLocalDescription(await pc.createOffer())
        offer = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        async with session.post(f"{signaling_server}/offer", json=offer) as resp:
            logging.info(f"Offer sent, server responded with {await resp.text()}")
        while True:
            logging.info("Waiting for answer...")
            await asyncio.sleep(2)
            async with session.get(f"{signaling_server}/answer") as resp:
                if resp.status == 200:
                    answer_json = await resp.json()
                    if answer_json:
                        answer = RTCSessionDescription(sdp=answer_json["sdp"], type=answer_json["type"])
                        await pc.setRemoteDescription(answer)
                        logging.info("Answer received and connection established.")
                        break
    else: # Role is "receive"
        while True:
            logging.info("Waiting for offer...")
            await asyncio.sleep(2)
            async with session.get(f"{signaling_server}/offer") as resp:
                 if resp.status == 200:
                    offer_json = await resp.json()
                    if offer_json:
                        offer = RTCSessionDescription(sdp=offer_json["sdp"], type=offer_json["type"])
                        await pc.setRemoteDescription(offer)
                        await pc.setLocalDescription(await pc.createAnswer())
                        answer = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
                        async with session.post(f"{signaling_server}/answer", json=answer) as resp_post:
                            logging.info(f"Answer sent, server responded with {await resp_post.text()}")
                        
                        async def display_composited_video():
                            while True:
                                await asyncio.sleep(1/30)
                                frames = [f for f in received_frames.values() if f is not None]
                                if len(frames) < 2:
                                    if len(frames) == 1: cv2.imshow("Received Video", frames[0])
                                    if cv2.waitKey(1) & 0xFF == ord('q'): break
                                    continue

                                face_frame, background_frame = None, None
                                green_pixels_0 = np.count_nonzero(cv2.inRange(frames[0], np.array([0, 250, 0]), np.array([5, 255, 5])))
                                green_pixels_1 = np.count_nonzero(cv2.inRange(frames[1], np.array([0, 250, 0]), np.array([5, 255, 5])))
                                if green_pixels_0 > green_pixels_1:
                                    face_frame, background_frame = frames[0], frames[1]
                                else:
                                    face_frame, background_frame = frames[1], frames[0]

                                mask = cv2.inRange(face_frame, np.array([0, 250, 0]), np.array([5, 255, 5]))
                                mask_inv = cv2.bitwise_not(mask)
                                fg = cv2.bitwise_and(face_frame, face_frame, mask=mask_inv)
                                bg = cv2.bitwise_and(background_frame, background_frame, mask=mask)
                                final_frame = cv2.add(bg, fg)

                                cv2.imshow("Received Video", final_frame)
                                if cv2.waitKey(1) & 0xFF == ord('q'): break
                        asyncio.ensure_future(display_composited_video())
                        break

    try:
        await asyncio.Event().wait()
    finally:
        await pc.close()
        await session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="U-LANC WebRTC Client")
    parser.add_argument("role", choices=["send", "receive"])
    parser.add_argument("--server", default="http://127.0.0.1:8080", help="Signaling server URL")
    args = parser.parse_args()
    pc = RTCPeerConnection()
    try:
        asyncio.run(run(pc, args.role, args.server))
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()