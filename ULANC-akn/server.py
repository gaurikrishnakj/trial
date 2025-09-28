# server.py (Corrected)
import asyncio
import json
import logging
from aiohttp import web
import aiohttp_cors

# Configure logging
logging.basicConfig(level=logging.INFO)

# A simple in-memory storage for the SDP offer and answer
offer = None
answer = None

async def handle_offer(request):
    """ Handles GET and POST requests for the offer. """
    global offer
    if request.method == "POST":
        data = await request.json()
        offer = data
        # Reset answer when a new offer is made
        global answer
        answer = None
        logging.info("Offer received and stored. Answer reset.")
        return web.Response(text="Offer stored", status=200)
    elif request.method == "GET":
        logging.info("Offer requested.")
        return web.json_response(offer)

async def handle_answer(request):
    """ Handles GET and POST requests for the answer. """
    global answer
    if request.method == "POST":
        data = await request.json()
        answer = data
        logging.info("Answer received and stored.")
        return web.Response(text="Answer stored", status=200)
    elif request.method == "GET":
        logging.info("Answer requested.")
        return web.json_response(answer)

# Create the web application
app = web.Application()

# Configure CORS for all routes
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
})

# --- This is the corrected section ---
# Create a resource for the '/offer' route and add CORS to it
offer_resource = cors.add(app.router.add_resource("/offer"))
# Add GET and POST method handlers to the resource
cors.add(offer_resource.add_route("GET", handle_offer))
cors.add(offer_resource.add_route("POST", handle_offer))

# Create a resource for the '/answer' route and add CORS to it
answer_resource = cors.add(app.router.add_resource("/answer"))
# Add GET and POST method handlers to the resource
cors.add(answer_resource.add_route("GET", handle_answer))
cors.add(answer_resource.add_route("POST", handle_answer))

# The problematic loop has been removed.

if __name__ == "__main__":
    logging.info("Starting signaling server at http://0.0.0.0:8080")
    web.run_app(app, host="0.0.0.0", port=8080)