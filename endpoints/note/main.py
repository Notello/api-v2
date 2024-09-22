"""
Runpod endpoint for ingest_note

This endpoint preforms any and all note ingestion,
which is called by the flask backend when new data is ready to be submitted.
"""

import runpod

from werkzeug.datastructures import FileStorage
from libnotello.NoteService import NoteService, NoteForm, IngestType

##
# Serverless Definition
##

runpod.serverless.start({"handler": NoteService.ingest})
