# app/api/v1/endpoints/companies.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_companies():
    return [
        "Next Level Office",
        "PrimeWorks",
        "BrightPath",
        "SummitWorks",
        "EverLink",
        "GoldBridge",
        "SilverLine",
        "TrueNorth",
        "BluePeak",
        "NexaWorks",
        "VistaLink",
        "Crystal Bay",
        "MetroLink",
        "StarBridge"
    ]
