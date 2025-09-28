import cv2
import mediapipe as mp
import numpy as np

# --- 1. INITIALIZATION ---

# Initialize MediaPipe Selfie Segmentation
mp_selfie_segmentation = mp.solutions.selfie_segmentation

# Initialize OpenCV Video Capture for the default webcam
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise IOError("Cannot open webcam")

# Set a desired window size
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
cap.set(cv2.CAP_PROP_FRAME_WIDTH, WINDOW_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WINDOW_HEIGHT)


# --- 2. MAIN PROCESSING LOOP ---

# The 'with' block ensures the segmentation resources are properly managed
with mp_selfie_segmentation.SelfieSegmentation(model_selection=0) as selfie_segmentation:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Ignoring empty camera frame.")
            continue

        # --- 3. CONTEXT-AWARENESS: IDENTIFY THE PERSON ---

        # Flip the frame horizontally for a later selfie-view display.
        # This makes the video feed act like a mirror.
        frame = cv2.flip(frame, 1)

        # Convert the BGR image to RGB before processing.
        # MediaPipe models expect images in RGB format.
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Process the frame and get the segmentation mask
        results = selfie_segmentation.process(rgb_frame)

        # The mask is a 2D array with values from 0.0 to 1.0.
        # A high value means a higher confidence that the pixel is part of the person.
        mask = results.segmentation_mask

        # --- 4. DIFFERENTIAL COMPRESSION: LOSSLESS/LOSSY SPLIT ---

        # Create a condition: True for pixels that are part of the person, False otherwise.
        # We use a threshold (e.g., 0.1) to create a sharp cutoff.
        # np.stack creates a 3-channel mask to match the frame's dimensions (BGR).
        condition = np.stack((mask,) * 3, axis=-1) > 0.5

        # Create the "lossy" background by applying a heavy Gaussian blur.
        # A larger kernel size (e.g., (99, 99)) results in a more intense blur,
        # simulating heavier data compression.
        blurred_background = cv2.GaussianBlur(frame, (99, 99), 0)

        # Use np.where to create the final output image.
        # If a pixel in 'condition' is True, use the corresponding pixel from the original 'frame'.
        # If it's False, use the pixel from the 'blurred_background'.
        output_frame = np.where(condition, frame, blurred_background)

        # --- 5. DISPLAY THE RESULT ---
        cv2.imshow('U-LANC: Adaptive Compression POC', output_frame)

        # Exit the loop if the 'q' key is pressed
        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

# --- 6. CLEANUP ---
cap.release()
cv2.destroyAllWindows()