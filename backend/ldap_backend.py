"""Seletor de backend LDAP/AD.

LDAP_BACKEND=ad (padrao) -> ad_auth (Active Directory Windows, bind UPN)
LDAP_BACKEND=openldap    -> ad_auth_slapd (OpenLDAP, busca DN + bind)
"""
import os
from dotenv import load_dotenv

load_dotenv()

_BACKEND = os.getenv("LDAP_BACKEND", "ad").strip().lower()

import importlib

if _BACKEND in ("openldap", "slapd"):
    _module_name = "ad_auth_slapd"
else:
    _module_name = "ad_auth"

_impl = importlib.import_module(_module_name)

_impl_attrs = {
    "authenticate_user", "create_or_update_local_user", "create_access_token",
    "create_refresh_token", "decode_token", "get_current_user",
    "get_current_user_from_token", "require_role", "get_role_mapping",
    "get_ad_connection", "ADAuthError", "AD_DOMAIN", "AD_BASE_DN", "AD_SERVER",
    "create_test_user", "create_test_tokens",
}

def __getattr__(name):
    return getattr(_impl, name)