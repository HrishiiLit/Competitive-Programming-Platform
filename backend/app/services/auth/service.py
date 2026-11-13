from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
import uuid
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_secure_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.models.user import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    Role,
    User,
    UserRole,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    @staticmethod
    async def get_or_create_default_role(db: AsyncSession, role_name: str = "PARTICIPANT") -> Role:
        stmt = select(Role).where(Role.name == role_name)
        result = await db.execute(stmt)
        role = result.scalar_one_or_none()
        if not role:
            role = Role(
                id=uuid.uuid4(),
                name=role_name,
                description=f"Standard {role_name.capitalize()} user",
            )
            db.add(role)
            await db.flush()
        return role

    @staticmethod
    async def register_user(
        db: AsyncSession,
        username: str,
        email: str,
        password: str,
        full_name: str,
        roles: Optional[List[str]] = None,
    ) -> User:
        # Check uniqueness
        stmt = select(User).where(or_(User.username == username, User.email == email))
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            if existing.username == username:
                raise ValueError("Username already taken")
            raise ValueError("Email already registered")

        password_hash = get_password_hash(password)
        user = User(
            id=uuid.uuid4(),
            username=username,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            account_status="ACTIVE",
            email_verified=False,
        )
        db.add(user)
        await db.flush()

        # Assign roles
        role_names = roles if roles else ["PARTICIPANT"]
        for r_name in role_names:
            role_obj = await AuthService.get_or_create_default_role(db, r_name)
            user_role = UserRole(
                user_id=user.id,
                role_id=role_obj.id,
            )
            db.add(user_role)

        await db.commit()

        # Reload with selectinload
        reload_stmt = (
            select(User)
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
            .where(User.id == user.id)
        )
        reload_res = await db.execute(reload_stmt)
        return reload_res.scalar_one()

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        username_or_email: str,
        password: str,
    ) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
            .where(or_(User.username == username_or_email, User.email == username_or_email))
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            return None

        if not verify_password(password, user.password_hash):
            return None

        if user.account_status != "ACTIVE":
            raise ValueError("Account is suspended or deactivated")

        return user

    @staticmethod
    async def create_tokens_for_user(
        db: AsyncSession,
        user: User,
        device_metadata: Optional[dict] = None,
    ) -> Tuple[str, str, int]:
        # Ensure user roles are loaded
        stmt = (
            select(User)
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
            .where(User.id == user.id)
        )
        res = await db.execute(stmt)
        full_user = res.scalar_one()

        roles = [ur.role.name for ur in full_user.user_roles if ur.role]

        access_token = create_access_token(
            subject=str(full_user.id),
            roles=roles,
            username=full_user.username,
        )

        raw_refresh_token = generate_secure_token()
        token_hash = hash_token(raw_refresh_token)
        expires_at = utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_record = RefreshToken(
            id=uuid.uuid4(),
            user_id=full_user.id,
            token_hash=token_hash,
            device_metadata=device_metadata or {},
            expires_at=expires_at,
            created_at=utc_now(),
        )
        db.add(refresh_record)
        await db.commit()

        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return access_token, raw_refresh_token, expires_in

    @staticmethod
    async def rotate_refresh_token(
        db: AsyncSession,
        raw_refresh_token: str,
        device_metadata: Optional[dict] = None,
    ) -> Tuple[str, str, int]:
        token_hash = hash_token(raw_refresh_token)

        stmt = (
            select(RefreshToken)
            .options(selectinload(RefreshToken.user).selectinload(User.user_roles).selectinload(UserRole.role))
            .where(RefreshToken.token_hash == token_hash)
        )
        result = await db.execute(stmt)
        token_record = result.scalar_one_or_none()

        if not token_record:
            raise ValueError("Invalid refresh token")

        now = utc_now()

        # Replay detection: If token was already revoked, revoke ALL user refresh tokens!
        if token_record.revoked_at is not None:
            revoke_all_stmt = select(RefreshToken).where(
                RefreshToken.user_id == token_record.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            rev_res = await db.execute(revoke_all_stmt)
            for r in rev_res.scalars().all():
                r.revoked_at = now
            await db.commit()
            raise ValueError("Refresh token replay detected. All sessions revoked for security.")

        expires_at = token_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now:
            raise ValueError("Refresh token expired")

        # Revoke current token
        token_record.revoked_at = now

        user = token_record.user
        roles = [ur.role.name for ur in user.user_roles if ur.role]

        new_access_token = create_access_token(
            subject=str(user.id),
            roles=roles,
            username=user.username,
        )

        new_raw_refresh_token = generate_secure_token()
        new_token_hash = hash_token(new_raw_refresh_token)
        new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        new_record = RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=new_token_hash,
            device_metadata=device_metadata or token_record.device_metadata,
            expires_at=new_expires_at,
            created_at=now,
        )
        db.add(new_record)
        await db.commit()

        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return new_access_token, new_raw_refresh_token, expires_in

    @staticmethod
    async def revoke_refresh_token(db: AsyncSession, raw_refresh_token: str) -> bool:
        token_hash = hash_token(raw_refresh_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await db.execute(stmt)
        token_record = result.scalar_one_or_none()
        if token_record and token_record.revoked_at is None:
            token_record.revoked_at = utc_now()
            await db.commit()
            return True
        return False
