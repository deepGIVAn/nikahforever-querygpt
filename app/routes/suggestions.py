from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["suggestions"])

@router.get("/suggest")
async def get_suggestions():
    """
    Returns a list of sample natural language questions (English/Hinglish)
    covering different tables to guide the user in testing the assistant.
    """
    return [
        {
            "category": "Subscriptions & Revenue",
            "questions": [
                "kitne logon ne premium liya?",
                "Which plan has the most subscribers?",
                "Total revenue this quarter"
            ]
        },
        {
            "category": "Users & Activity",
            "questions": [
                "How many users signed up last month?",
                "Show average profile completeness percentage",
                "Show all active users"
            ]
        },
        {
            "category": "Interactions",
            "questions": [
                "Top 10 most viewed profiles",
                "sabse zyada match kisko mila?",
                "Find premium users who never sent a message"
            ]
        },
        {
            "category": "Support",
            "questions": [
                "Open support tickets by category"
            ]
        }
    ]
