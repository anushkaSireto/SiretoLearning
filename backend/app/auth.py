from dataclasses import dataclass
import logging
import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    name: str | None = None

def _ensure_user(db: Session, user: CurrentUser) -> User:
    db_user = db.get(User, user.id)
    if db_user:
        return db_user

    db_user = User(id=user.id, email=user.email, name=user.name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info("User created user_id=%s email=%s", user.id, user.email)
    return db_user

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    if settings.auth_disabled:
        logger.warning("Authentication disabled; using local development user")
        return _ensure_user(
            db,
            CurrentUser(id="local-dev-user", email="dev@example.com", name="Local Dev"),
        )

    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        logger.warning("Authentication failed reason=missing_bearer_token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    jwks_url = settings.keycloak_jwks_url or f"{settings.keycloak_issuer}/protocol/openid-connect/certs"
    jwk_client = PyJWKClient(jwks_url)
    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.keycloak_issuer,
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        logger.warning("Authentication failed reason=invalid_token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    authorized_party = payload.get("azp")
    if authorized_party != settings.keycloak_audience:
        logger.warning("Authentication failed reason=unexpected_client azp=%s", authorized_party)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token issued for unexpected client")

    subject = payload.get("sub")
    email = payload.get("email")
    if not subject or not email:
        logger.warning("Authentication failed reason=missing_identity subject_present=%s email_present=%s", bool(subject), bool(email))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing user identity")

    logger.info("Authentication succeeded user_id=%s email=%s", subject, email)
    return _ensure_user(
        db,
        CurrentUser(
            id=subject,
            email=email,
            name=payload.get("name") or payload.get("preferred_username"),
        ),
    )
