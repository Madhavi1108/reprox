from fastapi import APIRouter

api_router = APIRouter()

# Sub-routers are included as each resource is implemented (build order
# steps 10, 15, 17). Intentionally empty at scaffold time so /health works
# before any domain endpoints exist.
