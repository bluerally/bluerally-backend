from typing import List
from typing import Optional, Any
from common.config import logger

from fastapi import APIRouter, status, Depends, Request, HTTPException, Query

from common.dependencies import get_current_user
from common.logging_configs import LoggingAPIRoute
from common.utils import convert_string_to_datetime
from parties.dto.request import (
    PartyDetailRequest,
    RefreshTokenRequest,
    PartyCommentPostRequest,
    PartyUpdateRequest,
)
from parties.dto.response import (
    PartyParticipationStatusChangeResponse,
    PartyCreateResponse,
)
from parties.dtos import (
    PartyListDetail,
    PartyDetail,
    PartyCommentDetail,
    PartyUpdateInfo,
)
from parties.models import Party
from parties.services import (
    PartyDetailService,
    PartyListService,
    PartyCommentService,
    PartyLikeService,
)
from parties.services import PartyParticipateService
from users.models import User, Sport, SportName_Pydantic

party_router = APIRouter(
    prefix="/api/party",
    route_class=LoggingAPIRoute,
)


@party_router.get(
    "/sports",
    response_model=List[SportName_Pydantic],
    status_code=status.HTTP_200_OK,
)
async def get_sports_list(request: Request) -> Any:
    try:
        sports_list = await SportName_Pydantic.from_queryset(Sport.all())
    except Exception as e:
        logger.error(f"[LAMBDA LOG]: Error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return sports_list


@party_router.post(
    "", response_model=PartyCreateResponse, status_code=status.HTTP_201_CREATED
)
async def create_party(
    request_data: PartyDetailRequest, user: User = Depends(get_current_user)
) -> PartyCreateResponse:
    try:
        gather_at_str = f"{request_data.gather_date}T{request_data.gather_time}:00+09:00"  # TODO 처리방법 변경 필요
        party = await Party.create(
            title=request_data.title,
            body=request_data.body,
            gather_at=convert_string_to_datetime(gather_at_str),
            place_id=request_data.place_id,
            place_name=request_data.place_name,
            address=request_data.address,
            longitude=request_data.longitude,
            latitude=request_data.latitude,
            participant_limit=request_data.participant_limit,
            participant_cost=request_data.participant_cost,
            sport_id=request_data.sport_id,
            organizer_user=user,
            notice=request_data.notice,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # 생성된 파티 정보를 응답
    return PartyCreateResponse(party_id=party.id)


@party_router.post(
    "/{party_id}", response_model=PartyUpdateInfo, status_code=status.HTTP_200_OK
)
async def update_party(
    body: PartyUpdateRequest, party_id: int, user: User = Depends(get_current_user)
) -> PartyUpdateInfo:
    try:
        service = await PartyDetailService.create(party_id=party_id)
        party_info = await service.update_party(user, body)
        return party_info
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@party_router.post(
    "/{party_id}/participate",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
)
async def participate_in_party(
    party_id: int, user: User = Depends(get_current_user)
) -> str:
    service = await PartyParticipateService.create(party_id, user)
    try:
        await service.participate()
        return "Participation requested successfully."
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@party_router.post(
    "/participants/{party_id}/status-change",
    response_model=PartyParticipationStatusChangeResponse,
    status_code=status.HTTP_200_OK,
)
async def participant_change_participation_status(
    party_id: int, body: RefreshTokenRequest, user: User = Depends(get_current_user)
) -> PartyParticipationStatusChangeResponse:
    new_status = body.new_status
    service = await PartyParticipateService.create(party_id, user)
    try:
        changed_participation = await service.participant_change_participation_status(
            new_status
        )
        return PartyParticipationStatusChangeResponse(
            participation_id=changed_participation.id, status=new_status
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@party_router.post(
    "/organizer/{party_id}/status-change/{participation_id}",
    response_model=PartyParticipationStatusChangeResponse,
    status_code=status.HTTP_200_OK,
)
async def organizer_change_participation_status(
    party_id: int,
    participation_id: int,
    body: RefreshTokenRequest,
    user: User = Depends(get_current_user),
) -> PartyParticipationStatusChangeResponse:
    new_status = body.new_status
    service = await PartyParticipateService.create(party_id, user)
    try:
        changed_participation = await service.organizer_change_participation_status(
            participation_id, new_status
        )
        return PartyParticipationStatusChangeResponse(
            participation_id=changed_participation.id,
            status=new_status,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@party_router.get(
    "/details/{party_id}",
    response_model=PartyDetail,
    status_code=status.HTTP_200_OK,
)
async def get_party_details(party_id: int, request: Request) -> PartyDetail:
    try:
        user = request.state.user
        service = await PartyDetailService.create(party_id)
        party_details = await service.get_party_details(user)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return party_details


@party_router.get(
    "/list", response_model=List[PartyListDetail], status_code=status.HTTP_200_OK
)
async def get_party_list(
    request: Request,
    sport_id: Optional[List[int]] = Query(None),
    is_active: Optional[bool] = None,
    gather_date_min: Optional[str] = None,
    gather_date_max: Optional[str] = None,
    search_query: Optional[str] = None,
    page: int = 1,
) -> List[PartyListDetail]:
    user = request.state.user
    service = PartyListService(user)
    party_list = await service.get_party_list(
        sport_id_list=sport_id,
        is_active=is_active,
        gather_date_min=gather_date_min,
        gather_date_max=gather_date_max,
        search_query=search_query,
        page=page,
    )
    return party_list


@party_router.get(
    "/{party_id}/comment",
    response_model=List[PartyCommentDetail],
    status_code=status.HTTP_200_OK,
)
async def get_party_comments(
    request: Request, party_id: int
) -> List[PartyCommentDetail]:
    user = request.state.user
    try:
        service = PartyCommentService(party_id, user)
        party_comments = await service.get_comments()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return party_comments


@party_router.post(
    "/{party_id}/comment",
    response_model=PartyCommentDetail,
    status_code=status.HTTP_201_CREATED,
)
async def post_party_comment(
    party_id: int, body: PartyCommentPostRequest, user: User = Depends(get_current_user)
) -> PartyCommentDetail:
    comment_content = body.content
    try:
        service = PartyCommentService(party_id, user)
        posted_comment = await service.post_comment(comment_content)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return posted_comment


@party_router.put(
    "/{party_id}/comment/{comment_id}",
    response_model=PartyCommentDetail,
    status_code=status.HTTP_200_OK,
)
async def change_party_comment(
    party_id: int,
    comment_id: int,
    body: PartyCommentPostRequest,
    user: User = Depends(get_current_user),
) -> Any:
    service = PartyCommentService(party_id, user)
    try:
        comment_content = body.content
        updated_comment = await service.change_comment(comment_id, comment_content)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return updated_comment


@party_router.delete(
    "/{party_id}/comment/{comment_id}",
    response_model=None,
    status_code=status.HTTP_200_OK,
)
async def delete_party_comment(
    party_id: int,
    comment_id: int,
    user: User = Depends(get_current_user),
) -> str:
    service = PartyCommentService(party_id, user)
    try:
        await service.delete_comment(comment_id)
        return f"Party comment {comment_id} successfully deleted"
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@party_router.post(
    "/like/{party_id}",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
)
async def add_liked_party(
    party_id: int,
    user: User = Depends(get_current_user),
) -> str:
    service = PartyLikeService(user)
    try:
        await service.party_like(party_id)
        return f"Party-{party_id} added to liked list"
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@party_router.delete(
    "/like/{party_id}",
    response_model=None,
    status_code=status.HTTP_200_OK,
)
async def cancel_liked_party(
    party_id: int,
    user: User = Depends(get_current_user),
) -> str:
    service = PartyLikeService(user)
    try:
        await service.cancel_party_like(party_id)
        return f"Party-{party_id} like canceled"
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@party_router.get(
    "/me/organized",
    response_model=List[PartyListDetail],
    status_code=status.HTTP_200_OK,
)
async def get_self_organized_party(
    page: int = 1,
    user: User = Depends(get_current_user),
) -> List[PartyListDetail]:
    try:
        service = PartyListService(user)
        party_list = await service.get_self_organized_parties(page=page)
        return party_list
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@party_router.get(
    "/me/participated",
    response_model=List[PartyListDetail],
    status_code=status.HTTP_200_OK,
)
async def get_participated_party(
    page: int = 1,
    user: User = Depends(get_current_user),
) -> List[PartyListDetail]:
    try:
        service = PartyListService(user)
        party_list = await service.get_participated_parties(page=page)
        return party_list
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
