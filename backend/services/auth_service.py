import logging
import os
import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

# Authority settings from environment variables
AUTHORITY = os.environ.get("OIDC_AUTHORITY", "https://auth.adolfrey.com/api")
CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "")
AUDIENCE = os.environ.get("OIDC_AUDIENCE", CLIENT_ID)
JWKS_URI = f"{AUTHORITY}/.well-known/jwks.json"

# PyJWKClient handles fetching and caching the keys automatically
jwks_client = PyJWKClient(JWKS_URI)

def verify_token(auth_header: str | None) -> dict:
    """
    Verifies the JWT token from the Authorization header using the 
    JWKS provided by the authentication authority.
    Returns the decoded token payload if valid.
    Raises ValueError if invalid, missing, or expired.
    """
    if not auth_header:
        raise ValueError("Authorization header is missing")

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise ValueError("Invalid Authorization header format. Expected 'Bearer <token>'")

    token = parts[1]
    
    try:
        # Get the signing key from the JWKS using the unverified header's kid
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Verify the token
        decode_kwargs = {
            "algorithms": ["RS256"],
            "issuer": AUTHORITY,
            "leeway": 300, # 5 minutes leeway for clock skew
            "options": {"verify_signature": True, "verify_aud": bool(AUDIENCE)}
        }
        
        if AUDIENCE:
            decode_kwargs["audience"] = AUDIENCE

        payload = jwt.decode(token, signing_key.key, **decode_kwargs)
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token: {str(e)}")
        raise ValueError(f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise ValueError("Token validation failed")
