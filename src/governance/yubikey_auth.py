#!/usr/bin/env python3
"""
YubiKey Authentication Module

This module provides YubiKey authentication functionality for the governance system.
It ensures that critical governance operations can only be performed by Mikael
using his physical YubiKey.
"""

import hmac
import logging
import os
import secrets
import time
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger("yubikey_auth")

class YubiKeyManager:
    """
    Manages YubiKey authentication for secure governance operations.
    This implementation focuses on HMAC-based OTP validation.
    """
    
    def __init__(self):
        """Initialize the YubiKey manager with primary and backup keys."""
        # In a real implementation, these would be loaded from secure storage
        # Here we simulate their presence
        
        # Primary YubiKey configuration
        self.primary_yubikey_id = os.environ.get("PRIMARY_YUBIKEY_ID", "primary-yubikey-test")
        self.primary_yubikey_secret = os.environ.get("PRIMARY_YUBIKEY_SECRET", "test-secret-key")
        self.primary_yubikey_counter = int(os.environ.get("PRIMARY_YUBIKEY_COUNTER", "0"))
        self.primary_yubikey_hotp = HOTP(self.primary_yubikey_secret)
        
        # Backup YubiKeys for emergency access
        self.backup_yubikeys = []
        for i in range(1, 3):  # Support for 2 backup keys
            key_id = os.environ.get(f"BACKUP_YUBIKEY{i}_ID")
            if key_id:
                self.backup_yubikeys.append({
                    "id": key_id,
                    "secret": os.environ.get(f"BACKUP_YUBIKEY{i}_SECRET", ""),
                    "counter": int(os.environ.get(f"BACKUP_YUBIKEY{i}_COUNTER", "0")),
                    "hotp": HOTP(os.environ.get(f"BACKUP_YUBIKEY{i}_SECRET", ""))
                })
        
        # Authentication session management
        self.auth_sessions = {}
        self.session_duration = 14 * 24 * 60 * 60  # 14 days in seconds
        
        logger.info("YubiKey authentication initialized")
    
    def validate_yubikey(self, otp: str) -> bool:
        """
        Validate a YubiKey OTP.
        
        Args:
            otp: One-time password from YubiKey
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Try primary YubiKey first
        for i in range(self.primary_yubikey_counter, self.primary_yubikey_counter + 20):
            expected_hotp = self.primary_yubikey_hotp.generate(i)
            if hmac.compare_digest(otp.encode('utf-8'), expected_hotp):
                # Update counter to prevent replay attacks
                self.primary_yubikey_counter = i + 1
                self._persist_counter_state()
                return True
        
        # Try backup YubiKeys if primary fails
        for backup_key in self.backup_yubikeys:
            for i in range(backup_key["counter"], backup_key["counter"] + 20):
                expected_hotp = backup_key["hotp"].generate(i)
                if hmac.compare_digest(otp.encode('utf-8'), expected_hotp):
                    # Update counter for the backup key
                    backup_key["counter"] = i + 1
                    self._persist_counter_state()
                    # Log use of backup key as this is unusual
                    logger.warning(f"Backup YubiKey {backup_key['id']} used for authentication")
                    return True
        
        logger.error("YubiKey validation failed - invalid OTP")
        return False
    
    def create_auth_session(self, user_id: str, yubikey_otp: str = None) -> Optional[str]:
        """
        Create an authentication session after successful YubiKey validation.
        
        Args:
            user_id: User identifier
            yubikey_otp: YubiKey one-time password
            
        Returns:
            Optional[str]: Session token if successful, None otherwise
        """
        # For Mikael, YubiKey validation is required
        if user_id in ["mhugo", "Mikael Hugo"] and yubikey_otp:
            if not self.validate_yubikey(yubikey_otp):
                logger.error("Authentication failed - invalid YubiKey OTP")
                return None
        
        # Generate session token
        session_token = secrets.token_urlsafe(32)
        expiry = time.time() + self.session_duration
        
        # Store session
        self.auth_sessions[session_token] = {
            "user_id": user_id,
            "created": time.time(),
            "expires": expiry,
            "yubikey_verified": yubikey_otp is not None
        }
        
        logger.info(f"Authentication session created for {user_id}")
        return session_token
    
    def validate_session(self, session_token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Validate an authentication session.
        
        Args:
            session_token: The session token to validate
            
        Returns:
            Tuple[bool, Optional[Dict]]: (is_valid, session_data)
        """
        if session_token not in self.auth_sessions:
            logger.error("Session validation failed - token not found")
            return False, None
        
        session = self.auth_sessions[session_token]
        
        # Check if session has expired
        if time.time() > session["expires"]:
            # Clean up expired session
            del self.auth_sessions[session_token]
            logger.error("Session validation failed - token expired")
            return False, None
        
        return True, session
    
    def require_yubikey_revalidation(self, session_token: str, operation: str) -> bool:
        """
        Determine if an operation requires fresh YubiKey validation.
        
        Args:
            session_token: The current session token
            operation: The operation being performed
            
        Returns:
            bool: True if revalidation is required, False otherwise
        """
        # High-risk operations always require fresh YubiKey validation
        high_risk_operations = [
            "approve_proposal", 
            "reject_proposal",
            "modify_security_settings",
            "update_system_config",
            "manage_yubikeys"
        ]
        
        if operation in high_risk_operations:
            return True
        
        # Check session age - require revalidation if over 1 hour
        is_valid, session = self.validate_session(session_token)
        if not is_valid:
            return True
        
        session_age = time.time() - session["created"]
        if session_age > 3600:  # 1 hour in seconds
            return True
        
        return False
    
    def _persist_counter_state(self) -> None:
        """
        Persist YubiKey counter state to prevent replay attacks across restarts.
        In a real implementation, this would write to a secure database.
        """
        # Update environment variables (just for demonstration)
        os.environ["PRIMARY_YUBIKEY_COUNTER"] = str(self.primary_yubikey_counter)
        
        for i, backup_key in enumerate(self.backup_yubikeys):
            os.environ[f"BACKUP_YUBIKEY{i+1}_COUNTER"] = str(backup_key["counter"])
        
        logger.info("YubiKey counter state persisted")


class HOTP:
    """
    HMAC-based One-Time Password implementation.
    This is a simplified version for demonstration purposes.
    In a real implementation, this would use a proper HOTP library.
    """
    
    def __init__(self, secret: str):
        """Initialize with a secret key."""
        self.secret = secret.encode('utf-8') if isinstance(secret, str) else secret
    
    def generate(self, counter: int) -> bytes:
        """
        Generate an HOTP value for a given counter.
        
        Args:
            counter: The counter value
            
        Returns:
            bytes: The HOTP value
        """
        # In a real implementation, this would follow RFC 4226
        # Here we use a simplified approach for demonstration
        counter_bytes = counter.to_bytes(8, byteorder='big')
        hmac_result = hmac.new(
            key=self.secret,
            msg=counter_bytes,
            digestmod='sha1'
        ).digest()
        
        # Simulate truncation to 6-8 digits as per YubiKey
        offset = hmac_result[-1] & 0xf
        binary = ((hmac_result[offset] & 0x7f) << 24 |
                 (hmac_result[offset + 1] & 0xff) << 16 |
                 (hmac_result[offset + 2] & 0xff) << 8 |
                 (hmac_result[offset + 3] & 0xff))
        
        hotp = str(binary % 1000000).zfill(6).encode('utf-8')
        return hotp


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    yubikey_manager = YubiKeyManager()
    
    # Simulate YubiKey OTP generation
    example_otp = yubikey_manager.primary_yubikey_hotp.generate(
        yubikey_manager.primary_yubikey_counter
    )
    
    # Validate the OTP
    is_valid = yubikey_manager.validate_yubikey(example_otp.decode('utf-8'))
    print(f"YubiKey validation: {'Success' if is_valid else 'Failed'}")
    
    # Create session after authentication
    session_token = yubikey_manager.create_auth_session(
        "mikael", 
        yubikey_manager.primary_yubikey_hotp.generate(
            yubikey_manager.primary_yubikey_counter
        ).decode('utf-8')
    )
    
    if session_token:
        # Validate session
        is_valid, session = yubikey_manager.validate_session(session_token)
        print(f"Session validation: {'Success' if is_valid else 'Failed'}")
        
        # Check if high-risk operation requires revalidation
        needs_revalidation = yubikey_manager.require_yubikey_revalidation(
            session_token, "approve_proposal"
        )
        print(f"Requires YubiKey revalidation: {'Yes' if needs_revalidation else 'No'}")