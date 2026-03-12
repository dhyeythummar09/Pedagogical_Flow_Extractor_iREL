import os
from dotenv import load_dotenv

# Load variables from a .env file in the project root
# On machines without a .env, set GEMINI_API_KEY in the shell, or it falls
# back to the hardcoded default below.
load_dotenv()

VIDEO_SOURCES = {
    "deadlock_os": "https://www.youtube.com/watch?v=rWFH6PLOIEI",
    "web_sockets": "https://www.youtube.com/watch?v=favi7avxIag",
    "ci_cd_pipeline": "https://www.youtube.com/watch?v=gLptmcuCx6Q",
    "rest_api": "https://www.youtube.com/watch?v=cJAyEOZQUQY",
    "nginx": "https://www.youtube.com/watch?v=b_B1BEShfBc"
}

# import GEMINI_API_KEY from .env
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
