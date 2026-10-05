"""Team invite workflow."""

from __future__ import annotations

import auth_store
import team_invite_store
import user_notification_store
from tests.postgres_test_case import PostgresStoreTestCase


class TeamInviteTest(PostgresStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        user_notification_store.bootstrap()
        team_invite_store.bootstrap()
        self.owner, self.owner_membership = auth_store.create_account_with_owner(
            email="owner@example.com",
            password="password123",
            display_name="Owner",
        )
        self.account_id = self.owner_membership["account_id"]
        self.invitee, self.invitee_membership = auth_store.create_account_with_owner(
            email="invitee@example.com",
            password="password123",
            display_name="Invitee",
        )

    def test_create_and_accept_invite(self) -> None:
        invite = team_invite_store.create_invite(
            self.account_id,
            email="invitee@example.com",
            role="operator",
            invited_by_user_id=self.owner["id"],
        )
        self.assertEqual(invite["status"], "pending")
        team_invite_store.sync_invites_for_user(self.invitee["id"], self.invitee["email"])
        notes = user_notification_store.list_for_user(self.invitee["id"])
        self.assertTrue(any(n.get("invite_id") == invite["id"] for n in notes))

        result = team_invite_store.accept_invite(invite["id"], user_id=self.invitee["id"])
        self.assertEqual(result["membership"]["role"], "operator")
        membership = auth_store.get_membership(self.account_id, self.invitee["id"])
        self.assertIsNotNone(membership)
        updated = team_invite_store.get_invite(invite["id"])
        assert updated
        self.assertEqual(updated["status"], "accepted")

    def test_decline_invite(self) -> None:
        invite = team_invite_store.create_invite(
            self.account_id,
            email="invitee@example.com",
            role="viewer",
            invited_by_user_id=self.owner["id"],
        )
        team_invite_store.sync_invites_for_user(self.invitee["id"], self.invitee["email"])
        self.assertTrue(team_invite_store.decline_invite(invite["id"], user_id=self.invitee["id"]))
        self.assertIsNone(auth_store.get_membership(self.account_id, self.invitee["id"]))


if __name__ == "__main__":
    import unittest

    unittest.main()
