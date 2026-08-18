# -*- coding: utf-8 -*-
"""
Test data factory
    - Random value generators for unique test data (avoids dirty data)
    - Builder pattern for GVA request payloads (user / authority)
    - All builders return a fresh dict on build(); chaining does not mutate shared state

Usage:
    from utils.data_factory import UserBuilder, AuthorityBuilder, DataFactory

    payload = (UserBuilder()
               .with_username(DataFactory.random_username())
               .with_password("Test1234!")
               .build())

Design notes:
    - Random generators use uuid4 hex slices for uniqueness; no faker dependency
    - Builders expose only GVA-required fields; extra fields via .with_extra(key, value)
    - Each build() returns a deep copy so callers can safely mutate the result
"""
import copy
import uuid


class DataFactory(object):
    """Random value generators for test data isolation"""

    @staticmethod
    def random_username(prefix="auto"):
        """Unique username: prefix_<8hex> (GVA allows alphanumeric + underscore)"""
        return "{}_{}".format(prefix, uuid.uuid4().hex[:8])

    @staticmethod
    def random_password():
        """Strong password meeting GVA rules: 8+ chars, upper + lower + digit + symbol"""
        # Fixed template with random suffix; GVA does not enforce complexity but keeps it realistic
        return "Pwd{}!Aa".format(uuid.uuid4().hex[:6])

    @staticmethod
    def random_nickname(prefix="nick"):
        return "{}_{}".format(prefix, uuid.uuid4().hex[:6])

    @staticmethod
    def random_phone():
        """Fake phone: 1xx xxxx xxxx (does not validate, GVA does not enforce)"""
        tail = uuid.uuid4().int % 100000000
        return "1{:08d}".format(tail)

    @staticmethod
    def random_email():
        return "auto_{}@test.local".format(uuid.uuid4().hex[:8])

    @staticmethod
    def random_authority_id():
        """High-range role ID (900000+) to avoid conflicts with real GVA roles"""
        return 900000 + (uuid.uuid4().int % 100000)

    @staticmethod
    def random_authority_name(prefix="auto_role"):
        return "{}_{}".format(prefix, uuid.uuid4().hex[:6])


class _BaseBuilder(object):
    """Base builder: holds a payload dict and returns a deep copy on build()"""

    def __init__(self, payload):
        self._payload = payload

    def with_extra(self, key, value):
        """Add an arbitrary extra field to the payload"""
        self._payload[key] = value
        return self

    def build(self):
        """Return a deep copy of the payload so callers can mutate safely"""
        return copy.deepcopy(self._payload)


class UserBuilder(_BaseBuilder):
    """
    Builder for GVA /user/admin_register payload.

    Default payload matches the real GVA SysUser fields:
        userName, passWord, authorityId, nickName, phone, email
    """

    def __init__(self):
        super(UserBuilder, self).__init__({
            "userName": "",
            "passWord": "",
            "authorityId": 888,
            "nickName": "",
            "phone": "",
            "email": "",
        })

    # Field setters (chainable)

    def with_username(self, username):
        self._payload["userName"] = username
        # Default nickName follows userName if not explicitly set
        if not self._payload.get("nickName"):
            self._payload["nickName"] = username
        return self

    def with_password(self, password):
        self._payload["passWord"] = password
        return self

    def with_authority_id(self, authority_id):
        # GVA backend field is uint; ensure int
        self._payload["authorityId"] = int(authority_id)
        return self

    def with_nick_name(self, nick_name):
        self._payload["nickName"] = nick_name
        return self

    def with_phone(self, phone):
        self._payload["phone"] = phone
        return self

    def with_email(self, email):
        self._payload["email"] = email
        return self

    # Convenience: fill all random fields at once

    def random(self):
        """Populate all fields with random valid values (except authorityId=888)"""
        username = DataFactory.random_username()
        return (self
                .with_username(username)
                .with_password(DataFactory.random_password())
                .with_nick_name(DataFactory.random_nickname())
                .with_phone(DataFactory.random_phone())
                .with_email(DataFactory.random_email()))


class AuthorityBuilder(_BaseBuilder):
    """
    Builder for GVA /authority/createAuthority and /authority/updateAuthority payload.

    Default payload matches the real GVA SysAuthority fields:
        authorityId, authorityName, parentId
    """

    def __init__(self):
        super(AuthorityBuilder, self).__init__({
            "authorityId": 0,
            "authorityName": "",
            "parentId": 0,
        })

    def with_authority_id(self, authority_id):
        self._payload["authorityId"] = int(authority_id)
        return self

    def with_authority_name(self, authority_name):
        self._payload["authorityName"] = authority_name
        return self

    def with_parent_id(self, parent_id):
        self._payload["parentId"] = int(parent_id)
        return self

    def random(self):
        """Populate with random valid values (parentId=0 root role)"""
        return (self
                .with_authority_id(DataFactory.random_authority_id())
                .with_authority_name(DataFactory.random_authority_name())
                .with_parent_id(0))
