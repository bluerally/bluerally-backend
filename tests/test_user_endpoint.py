import io
from datetime import datetime, timedelta
from typing import Callable, Any, Coroutine
from unittest.mock import patch, Mock, AsyncMock
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

# from common.config import AWS_S3_URL
from pytest import MonkeyPatch
from starlette import status

from common.dependencies import get_current_user
from notifications.models import Notification, NotificationRead
from parties.models import Party, PartyLike
from users.auth import GoogleAuth
from users.models import User, UserToken, Sport, UserInterestedSport


@pytest.mark.asyncio
async def test_get_social_login_redirect_url(client: AsyncClient) -> None:
    response = await client.get("/api/user/auth/redirect-url/google")
    assert response.status_code == status.HTTP_200_OK
    query_params = {
        "client_id": GoogleAuth.CLIENT_ID,
        "redirect_uri": GoogleAuth.REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    }
    _redirect_url = f"{GoogleAuth.AUTHORIZATION_URL}?{urlencode(query_params)}"
    assert response.json()["redirect_url"] == _redirect_url


MOCKED_GOOGLE_USER_INFO = {
    "iss": "https://accounts.google.com",
    "azp": "some-client-id.apps.googleusercontent.com",
    "aud": "some-client-id.apps.googleusercontent.com",
    "sub": "some-unique-id",
    "email": "user@example.com",
    "email_verified": True,
    "at_hash": "some-hash",
    "name": "John Doe",
    "picture": "https://profile.image.url",
    "given_name": "John",
    "family_name": "Doe",
    "locale": "en",
    "iat": 1616161616,
    "exp": 1616165216,
}


@patch("users.auth.id_token.verify_oauth2_token", return_value=MOCKED_GOOGLE_USER_INFO)
@patch("httpx.AsyncClient.post")
@pytest.mark.asyncio
async def test_social_auth_google(
    mock_post: Mock, mock_verify: Mock, client: AsyncClient
) -> None:
    mock_post.return_value.json = lambda: {
        "access_token": "mock_access_token",
        "id_token": "mock_id_token",
        "expires_in": 3599,
        "token_type": "Bearer",
    }

    response = await client.get("/api/user/auth/google", params={"code": "testcode"})

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT


@pytest.mark.asyncio
async def test_refresh_token_endpoint(client: AsyncClient) -> None:
    # 테스트 데이터 세팅
    user = await User.create(
        id=1,
        email="fakeemail@gmail.com",
        sns_id="some_sns_id",
        name="Test User",
        profile_image="path/to/image",
    )
    refresh_token = "test_refresh_token"
    await UserToken.create(
        user=user,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_at=datetime.now(ZoneInfo("UTC")) + timedelta(days=1),
    )

    # 의존성 오버라이드 설정
    from main import app

    app.dependency_overrides[get_current_user] = lambda: user

    # API 호출
    response = await client.post(
        "/api/user/auth/token/refresh", json={"refresh_token": refresh_token}
    )

    # 응답 검증
    assert response.status_code == status.HTTP_201_CREATED
    assert (
        await UserToken.get_or_none(
            user=user, refresh_token=refresh_token, is_active=True
        )
        is not None
    )

    # 오버라이드 초기화
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_success_logout(client: AsyncClient) -> None:
    user = await User.create(
        id=3,
        email="fakeemail2@gmail.com",
        sns_id="some_sns_id",
        name="Test User",
        profile_image="path/to/image",
    )
    refresh_token = "test_refresh_token"
    await UserToken.create(
        user=user,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_at=datetime.now(ZoneInfo("UTC")) + timedelta(days=1),
    )

    # 의존성 오버라이드 설정
    from main import app

    app.dependency_overrides[get_current_user] = lambda: user

    # API 호출
    response = await client.post("/api/user/auth/logout")

    # 응답 검증
    assert response.status_code == 200
    assert await UserToken.get_or_none(user=user, is_active=True) is None

    # 오버라이드 초기화
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_success_get_liked_parties(client: AsyncClient) -> None:
    sport = await Sport.create(name="Sport")
    user = await User.create(
        email="fakeemail2@gmail.com",
        sns_id="sns_id",
        name="Test User",
        profile_image="https://path/to/image",
    )
    organizer = await User.create(
        email="organizer@gmail.com",
        sns_id="organizer_sns_id",
        name="Test organizer",
        profile_image="https://path/to/image",
    )
    party_1 = await Party.create(
        title="Test Party",
        created_at=datetime.now(),
        gather_at=datetime.now() + timedelta(days=2),
        body="Test Party Body",
        organizer_user=organizer,
        sport=sport,
        place_id=123215213,
        place_name="딥스테이션",
        address="경기도 용신시 처인구 784-2",
        longitude=float(37.2805605),
        latitude=float(127.1997416),
    )
    party_2 = await Party.create(
        title="Test Party2",
        body="Test Party Body",
        created_at=datetime.now(),
        gather_at=datetime.now() + timedelta(days=2),
        organizer_user=organizer,
        sport=sport,
        place_id=123215213,
        place_name="딥스테이션",
        address="경기도 용신시 처인구 784-2",
        longitude=float(37.2805605),
        latitude=float(127.1997416),
    )
    await PartyLike.create(user=user, party=party_1)
    await PartyLike.create(user=user, party=party_2)

    # 의존성 오버라이드 설정
    from main import app

    app.dependency_overrides[get_current_user] = lambda: user

    # API 호출
    response = await client.get("/api/user/party/like")
    response_json = response.json()

    # 응답 검증
    assert response.status_code == 200
    assert len(response_json) == 2

    # 오버라이드 초기화
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_success_get_self_profile(client: AsyncClient) -> None:
    sport_1 = await Sport.create(name="Sport1")
    sport_2 = await Sport.create(name="Sport2")
    sport_3 = await Sport.create(name="Sport3")
    user = await User.create(
        email="fakeemail2@gmail.com",
        sns_id="sns_id",
        name="Test User",
        introduction="안녕하세요",
        profile_image="https://path/to/image",
    )
    await UserInterestedSport.create(user=user, sport=sport_1)
    await UserInterestedSport.create(user=user, sport=sport_2)
    await UserInterestedSport.create(user=user, sport=sport_3)

    # 의존성 오버라이드 설정
    from main import app

    app.dependency_overrides[get_current_user] = lambda: user

    # API 호출
    response = await client.get("/api/user/me")

    # 응답 검증
    assert response.status_code == 200

    # 오버라이드 초기화
    app.dependency_overrides.clear()


@pytest.fixture
def mock_s3_upload(monkeypatch: MonkeyPatch) -> Callable[[], Coroutine[Any, Any, str]]:
    async def mock_upload_file(*args: Any, **kwargs: Any) -> str:
        return "user1/profile-image/fakeimage.jpg"

    monkeypatch.setattr("users.services.s3_upload_file", mock_upload_file)
    return mock_upload_file


@pytest.mark.asyncio
async def test_update_self_profile(
    client: AsyncClient, mock_s3_upload: AsyncMock
) -> None:
    # 유저와 관심 스포츠 생성
    user = await User.create(
        email="user@example.com",
        name="Test User",
        profile_image="user/1/original.jpg",
    )
    sport_1 = await Sport.create(name="Freediving")
    sport_2 = await Sport.create(name="Surfing")

    # 의존성 오버라이드 설정
    from main import app

    app.dependency_overrides[get_current_user] = lambda: user

    # 업데이트할 프로필 정보
    profile_data = {
        "name": "Updated Name",
        "introduction": "Updated introduction",
        "email": "test-mail@gmail.com",
        "interested_sports_ids": [sport_1.id, sport_2.id],
    }

    # API 호출
    response = await client.post("/api/user/me", json=profile_data)

    # 응답 검증
    assert response.status_code == status.HTTP_201_CREATED

    updated_user = await User.get(id=user.id)
    assert updated_user.name == "Updated Name"
    interested_sports = await UserInterestedSport.filter(user=user).all()
    assert len(interested_sports) == 2
    assert response.json()["interested_sports"][0] == {
        "id": sport_1.id,
        "name": sport_1.name,
    }

    # 변경된 profile로 조회
    get_profile_response = await client.get("/api/user/me")
    assert get_profile_response.status_code == status.HTTP_200_OK
    assert get_profile_response.json().get("name") == "Updated Name"
    assert get_profile_response.json().get("introduction") == "Updated introduction"

    # 오버라이드 초기화
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_self_profile_image(
    client: AsyncClient, mock_s3_upload: AsyncMock
) -> None:
    # 유저와 관심 스포츠 생성
    user = await User.create(
        email="user@example.com",
        name="Test User",
        profile_image="user/1/original.jpg",
    )

    # 의존성 오버라이드 설정
    from main import app

    app.dependency_overrides[get_current_user] = lambda: user

    fake_image = io.BytesIO(b"test image")
    fake_image.seek(0)
    files = {
        "profile_image": ("mock_image.jpg", fake_image, "image/jpeg"),
    }

    # API 호출
    response = await client.post("/api/user/me/profile-image", files=files)

    # 응답 검증
    assert response.status_code == status.HTTP_201_CREATED

    updated_user = await User.get(id=user.id)
    assert (
        updated_user.profile_image == "user1/profile-image/fakeimage.jpg"
    )  # Mock에서 반환된 URL

    # 오버라이드 초기화
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_success_get_notifications(client: AsyncClient) -> None:
    user = await User.create(
        email="fakeemail2@gmail.com",
        sns_id="sns_id",
        name="Test User",
        profile_image="https://path/to/image",
    )
    sport = await Sport.create(name="Freediving")
    party = await Party.create(
        title="Freediving Party",
        body="Freediving Party body",
        organizer_user=user,
        gather_at=datetime.now(ZoneInfo("UTC")) + timedelta(days=2),
        participant_limit=5,
        participant_cost=200,
        sport=sport,
        notice="카톡 아이디는 audwls624",
    )
    await Notification.create(type="all", message="전체 공지 1", is_global=True)
    notice_2 = await Notification.create(
        type="party",
        related_id=party.id,
        message="파티 공지1",
        target_user=user,
        classification="details_updated",
    )
    notice_3 = await Notification.create(
        type="all", message="전체 공지 2", is_global=True
    )
    await Notification.create(
        type="party",
        related_id=party.id,
        message="파티 공지1",
        target_user=user,
        classification="details_updated",
    )

    await NotificationRead.create(user=user, notification=notice_2)
    await NotificationRead.create(user=user, notification=notice_3)

    # 의존성 오버라이드 설정
    from main import app

    app.dependency_overrides[get_current_user] = lambda: user
    # API 호출
    response = await client.get("/api/user/notifications")
    # 응답 검증
    assert response.status_code == 200
    assert response.json()["notifications"][0].get("related_id") == party.id
    assert response.json()["total_pages"] == 1


@pytest.mark.asyncio
async def test_success_read_notifications(client: AsyncClient) -> None:
    user = await User.create(
        email="fakeemail2@gmail.com",
        sns_id="sns_id",
        name="Test User",
        profile_image="https://path/to/image",
    )

    noti_1 = await Notification.create(
        type="all", message="전체 공지 1", is_global=True
    )
    noti_2 = await Notification.create(
        type="all", message="전체 공지 2", is_global=True
    )

    # 의존성 오버라이드 설정
    from main import app

    app.dependency_overrides[get_current_user] = lambda: user
    # API 호출
    response = await client.post(
        "/api/user/notifications/read",
        json={"read_notification_list": [noti_1.id, noti_2.id]},
    )
    # 응답 검증
    assert response.status_code == 201
    assert await NotificationRead.filter(notification=noti_1).exists()
    assert await NotificationRead.filter(notification=noti_2).exists()


@pytest.mark.asyncio
async def test_success_get_user_profile(client: AsyncClient) -> None:
    sport_1 = await Sport.create(name="Sport1")
    sport_2 = await Sport.create(name="Sport2")
    sport_3 = await Sport.create(name="Sport3")
    user = await User.create(
        email="fakeemail2@gmail.com",
        sns_id="sns_id",
        name="Test User",
        introduction="안녕하세요",
        profile_image="https://path/to/image",
    )
    await UserInterestedSport.create(user=user, sport=sport_1)
    await UserInterestedSport.create(user=user, sport=sport_2)
    await UserInterestedSport.create(user=user, sport=sport_3)

    # API 호출
    response = await client.get(f"/api/user/profile/{user.id}")

    # 응답 검증
    assert response.status_code == 200
    assert response.json().get("introduction") == "안녕하세요"
