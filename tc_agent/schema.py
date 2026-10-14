"""Claude가 돌려줄 결과의 구조. 이 구조 그대로 Markdown 리포트와 엑셀을 만든다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VariableMapping(BaseModel):
    technical_variable: str = Field(description="기술 변수/조건식 (예: 멤버십 가입 여부, 결제금액 >= 5000)")
    business_meaning: str = Field(description="서비스 화면/버튼/상태값에서의 의미")


class TestCategory(BaseModel):
    name: str = Field(description="테스트 그룹 이름")
    entry_point: str = Field(description="사용자 진입 경로 (예: 홈 > 혜택탭 > 이벤트 배너 Tap)")


class Analysis(BaseModel):
    domain: str
    core_objective: str
    mappings: list[VariableMapping]
    logic_summary: list[str] = Field(description="'만약 [조건]이면 [결과]가 발생한다' 형태의 명제 목록")
    test_objectives: list[str]
    categories: list[TestCategory]


class TestCase(BaseModel):
    tc_id: str = Field(description="TC-001 형식")
    category: str
    title: str = Field(description="한 줄 요약")
    case_type: Literal["Positive", "Negative"]
    priority: Literal["High", "Medium", "Low"]
    test_path: str = Field(description="진입 경로")
    precondition: str = Field(description="계정 상태, 시점 등 사전 조건")
    steps: str = Field(description="번호를 붙인 수행 동작")
    expected_result: str
    source: str = Field(description="근거가 된 화면/영역 이름과 타일 라벨")


class TestSuite(BaseModel):
    analysis: Analysis
    test_cases: list[TestCase]
    open_questions: list[str] = Field(description="기획서에서 모호하거나 누락되어 기획 확인이 필요한 사항")
