import pytest
from httpx import AsyncClient

from common.dependencies import get_current_user
from users.models import User, Sport
from datetime import datetime, UTC, timedelta
from parties.models import Party, PartyParticipant, ParticipationStatus


@pytest.mark.asyncio
async def test_success_party_create(client: AsyncClient) -> None:
    user = await User.create(
        email="partyorg6@gmail.com",
        sns_id="some_sns_id",
        name="Party Organizer User",
        profile_image="https://path/to/image",
    )
    sport = await Sport.create(name="프리다이빙")

    # 의존성 오버라이드 설정
    from main import app

    app.dependency_overrides[get_current_user] = lambda: user

    request_data = {
        "title": "test title",
        "body": "test body",
        "gather_at": "2023-12-27T17:13:40+09:00",
        "due_at": "2023-12-27T00:00:00+09:00",
        "place_id": 123314252353,
        "place_name": "딥스테이션",
        "address": "경기도 용인시 처인구 90길 90",
        "longitude": 34.12,
        "latitude": 55.123,
        "participant_limit": 4,
        "participant_cost": 66000,
        "sport_id": sport.id,
    }
    # API 호출
    response = await client.post("/api/party/", json=request_data)

    # 응답 검증
    assert response.status_code == 200
    assert Party.get_or_none(title=request_data["title"]) is not None

    # 오버라이드 초기화
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_success_party_participate(client: AsyncClient) -> None:
    organizer_user = await User.create(name="Organizer User")
    test_party = await Party.create(
        title="Test Party",
        organizer_user=organizer_user,
        due_at=datetime.now(UTC) + timedelta(days=1),
    )
    test_user = await User.create(name="Test User")

    from main import app

    app.dependency_overrides[get_current_user] = lambda: test_user

    response = await client.post(f"/api/party/{test_party.id}/participate")

    assert response.status_code == 200
    assert (
        await PartyParticipant.get_or_none(
            party=test_party,
            participant_user=test_user,
            status=ParticipationStatus.PENDING,
        )
        is not None
    )

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_organizer_accepts_participation(client: AsyncClient) -> None:
    organizer_user = await User.create(name="Organizer User")
    participant_user = await User.create(name="Participant User")
    test_party = await Party.create(title="Test Party", organizer_user=organizer_user)

    # 참가 신청 생성
    participation = await PartyParticipant.create(
        party=test_party, participant_user=participant_user
    )

    from main import app

    # 파티장 권한으로 로그인
    app.dependency_overrides[get_current_user] = lambda: organizer_user

    # 참가 신청 수락
    response = await client.post(
        f"/api/party/organizer/{test_party.id}/status-change/{participation.id}",
        json={"new_status": ParticipationStatus.APPROVED.value},
    )
    assert response.status_code == 200
    changed_participation = await PartyParticipant.get_or_none(id=participation.id)
    assert changed_participation is not None
    assert changed_participation.status == ParticipationStatus.APPROVED


@pytest.mark.asyncio
async def test_success_participant_cancel_participation(client: AsyncClient) -> None:
    organizer_user = await User.create(name="Organizer User")
    participant_user = await User.create(name="Participant User")
    test_party = await Party.create(title="Test Party", organizer_user=organizer_user)

    # 참가 신청 생성
    participation = await PartyParticipant.create(
        party=test_party,
        participant_user=participant_user,
        status=ParticipationStatus.APPROVED,
    )

    from main import app

    app.dependency_overrides[get_current_user] = lambda: participant_user

    # 참가 신청 수락
    response = await client.post(
        f"/api/party/participants/{test_party.id}/status-change",
        json={"new_status": ParticipationStatus.CANCELLED.value},
    )
    assert response.status_code == 200
    changed_participation = await PartyParticipant.get_or_none(id=participation.id)
    assert changed_participation is not None
    assert changed_participation.status == ParticipationStatus.CANCELLED


@pytest.mark.asyncio
async def test_get_party_details_success(client: AsyncClient) -> None:
    # 더미 데이터 생성
    organizer_user = await User.create(
        name="Organizer User", profile_image="http://example.com/image.jpg"
    )
    test_party = await Party.create(
        title="Test Party",
        body="Test Party body",
        organizer_user=organizer_user,
        gather_at=datetime.now(UTC) + timedelta(days=1),
        due_at=datetime.now(UTC) + timedelta(days=2),
        participant_limit=10,
        participant_cost=100,
        sport=await Sport.create(name="Freediving"),
    )
    approved_participant_user_1 = await User.create(
        name="Participated User 1", profile_image="http://example.com/image2.jpg"
    )
    approved_participant_user_2 = await User.create(
        name="Participated User 2", profile_image="http://example.com/image3.jpg"
    )
    approved_participant_user_3 = await User.create(
        name="Participated User 3", profile_image="http://example.com/image4.jpg"
    )

    pending_participant_user_1 = await User.create(
        name="Pending Participant User 1", profile_image="http://example.com/image5.jpg"
    )
    pending_participant_user_2 = await User.create(
        name="Pending Participant User 2", profile_image="http://example.com/image6.jpg"
    )
    await PartyParticipant.create(
        party=test_party,
        participant_user=approved_participant_user_1,
        status=ParticipationStatus.APPROVED,
    )
    await PartyParticipant.create(
        party=test_party,
        participant_user=approved_participant_user_2,
        status=ParticipationStatus.APPROVED,
    )
    await PartyParticipant.create(
        party=test_party,
        participant_user=approved_participant_user_3,
        status=ParticipationStatus.APPROVED,
    )
    await PartyParticipant.create(
        party=test_party,
        participant_user=pending_participant_user_1,
        status=ParticipationStatus.PENDING,
    )
    await PartyParticipant.create(
        party=test_party,
        participant_user=pending_participant_user_2,
        status=ParticipationStatus.PENDING,
    )

    # 의존성 오버라이드 설정
    from main import app

    app.dependency_overrides[get_current_user] = lambda: organizer_user

    # API 호출
    response = await client.get(f"/api/party/details/{test_party.id}")
    response_data = response.json()
    data = response_data["data"]
    # 응답 검증
    assert response.status_code == 200
    assert data["sport_name"] == "Freediving"
    assert data["participants_info"] == "3/10"
    assert data["organizer_profile"]["name"] == "Organizer User"
    assert len(data["approved_participants"]) == 3
    assert len(data["pending_participants"]) == 2

    # 의존성 오버라이드 초기화
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_party_list_success(client: AsyncClient) -> None:
    # 더미 데이터 생성
    organizer_user_1 = await User.create(
        name="Organizer User 1", profile_image="http://example.com/image1.jpg"
    )
    organizer_user_2 = await User.create(
        name="Organizer User 2", profile_image="http://example.com/image2.jpg"
    )
    sport_1 = await Sport.create(name="Freediving")
    sport_2 = await Sport.create(name="Scuba Diving")

    await Party.create(
        title="Freediving Party",
        body="Freediving Party body",
        organizer_user=organizer_user_1,
        gather_at=datetime.now(UTC) + timedelta(days=3),
        due_at=datetime.now(UTC) + timedelta(days=4),
        participant_limit=5,
        participant_cost=200,
        sport=sport_1,
    )
    await Party.create(
        title="Scuba Diving Party",
        body="Scuba Diving Party body",
        organizer_user=organizer_user_2,
        gather_at=datetime.now(UTC) + timedelta(days=5),
        due_at=datetime.now(UTC) + timedelta(days=6),
        participant_limit=6,
        participant_cost=300,
        sport=sport_2,
    )

    # 의존성 오버라이드 설정
    from main import app

    app.dependency_overrides[get_current_user] = lambda: organizer_user_1

    # API 호출
    response = await client.get("/api/party/list")
    response_data = response.json()
    parties = response_data["data"]

    # 응답 검증
    assert response.status_code == 200
    assert len(parties) == 2

    # 의존성 오버라이드 초기화
    app.dependency_overrides.clear()
