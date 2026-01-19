from typing import Any, Dict, Optional

from usaspending_mcp.router import Router


class AnswerAwardSpendingQuestionTool:
    def __init__(self, router: Router):
        self.router = router

    def execute(self, question: str, debug: bool = False, request_id: Optional[str] = None) -> Dict[str, Any]:
        return self.router.route_request(question, debug, request_id)
