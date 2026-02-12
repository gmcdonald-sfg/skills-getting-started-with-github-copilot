"""
Tests for the Mergington High School Activities API
"""

import pytest
from fastapi.testclient import TestClient
from urllib.parse import quote
from copy import deepcopy

from app import app, activities

# Store the original activities state
_original_activities = deepcopy(activities)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities to original state before each test"""
    activities.clear()
    activities.update(deepcopy(_original_activities))
    yield


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


class TestGetActivities:
    """Tests for the /activities endpoint"""

    def test_get_activities_returns_all_activities(self, client):
        """Test that GET /activities returns all available activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) > 0
        
        # Check that at least the expected activities exist
        expected_activities = ["Chess Club", "Programming Class", "Gym Class"]
        for activity in expected_activities:
            assert activity in data

    def test_activities_have_required_fields(self, client):
        """Test that each activity has all required fields"""
        response = client.get("/activities")
        data = response.json()
        
        required_fields = ["description", "schedule", "max_participants", "participants"]
        for activity_name, activity_details in data.items():
            for field in required_fields:
                assert field in activity_details, f"Activity {activity_name} missing field {field}"
            
            assert isinstance(activity_details["participants"], list)
            assert isinstance(activity_details["max_participants"], int)

    def test_participants_is_list(self, client):
        """Test that participants field is always a list"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_details in data.values():
            assert isinstance(activity_details["participants"], list)


class TestSignup:
    """Tests for the /activities/{activity_name}/signup endpoint"""

    def test_signup_new_participant(self, client):
        """Test signing up a new participant to an activity"""
        activity = "Chess Club"
        response = client.post(
            f"/activities/{quote(activity)}/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in data["message"]
        assert "Chess Club" in data["message"]

    def test_signup_duplicate_participant_fails(self, client):
        """Test that signing up the same participant twice fails"""
        email = "duplicate@mergington.edu"
        activity = "Chess Club"
        
        # First signup should succeed
        response1 = client.post(
            f"/activities/{quote(activity)}/signup?email={email}"
        )
        assert response1.status_code == 200
        
        # Second signup should fail
        response2 = client.post(
            f"/activities/{quote(activity)}/signup?email={email}"
        )
        assert response2.status_code == 400
        assert "already signed up" in response2.json()["detail"]

    def test_signup_nonexistent_activity_fails(self, client):
        """Test that signing up for a nonexistent activity fails"""
        activity = "Nonexistent Activity"
        response = client.post(
            f"/activities/{quote(activity)}/signup?email=test@mergington.edu"
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_signup_adds_participant_to_list(self, client):
        """Test that signup actually adds the participant to the activity"""
        email = "tracker@mergington.edu"
        activity = "Tennis Club"
        
        # Get initial count
        response_before = client.get("/activities")
        before_count = len(response_before.json()[activity]["participants"])
        
        # Sign up
        client.post(f"/activities/{quote(activity)}/signup?email={email}")
        
        # Get updated count
        response_after = client.get("/activities")
        after_count = len(response_after.json()[activity]["participants"])
        
        assert after_count == before_count + 1
        assert email in response_after.json()[activity]["participants"]

    def test_signup_fails_when_activity_is_full(self, client):
        """Test that signup fails when activity is at max capacity"""
        activity = "Tennis Club"
        
        # Get current activity state
        response = client.get("/activities")
        activity_data = response.json()[activity]
        max_participants = activity_data["max_participants"]
        current_count = len(activity_data["participants"])
        
        # Fill up remaining spots
        spots_to_fill = max_participants - current_count
        for i in range(spots_to_fill):
            email = f"filler{i}@mergington.edu"
            response = client.post(
                f"/activities/{quote(activity)}/signup?email={email}"
            )
            assert response.status_code == 200
        
        # Try to sign up one more person - should fail
        response = client.post(
            f"/activities/{quote(activity)}/signup?email=overflow@mergington.edu"
        )
        assert response.status_code == 400
        assert "full" in response.json()["detail"].lower()


class TestUnregister:
    """Tests for the /activities/{activity_name}/unregister endpoint"""

    def test_unregister_existing_participant(self, client):
        """Test unregistering an existing participant"""
        email = "remove_me@mergington.edu"
        activity = "Debate Club"
        
        # First, sign up
        client.post(f"/activities/{quote(activity)}/signup?email={email}")
        
        # Then unregister
        response = client.post(
            f"/activities/{quote(activity)}/unregister?email={email}"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        assert activity in data["message"]

    def test_unregister_nonexistent_participant_fails(self, client):
        """Test that unregistering a participant not in the activity fails"""
        email = "never_signed_up@mergington.edu"
        activity = "Chess Club"
        
        response = client.post(
            f"/activities/{quote(activity)}/unregister?email={email}"
        )
        assert response.status_code == 400
        assert "not signed up" in response.json()["detail"]

    def test_unregister_nonexistent_activity_fails(self, client):
        """Test that unregistering from a nonexistent activity fails"""
        activity = "Fake Activity"
        response = client.post(
            f"/activities/{quote(activity)}/unregister?email=test@mergington.edu"
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_unregister_removes_participant_from_list(self, client):
        """Test that unregister actually removes the participant"""
        email = "temp_member@mergington.edu"
        activity = "Robotics Club"
        
        # Sign up
        client.post(f"/activities/{quote(activity)}/signup?email={email}")
        
        # Verify they're in the list
        response_before = client.get("/activities")
        assert email in response_before.json()[activity]["participants"]
        
        # Unregister
        client.post(f"/activities/{quote(activity)}/unregister?email={email}")
        
        # Verify they're no longer in the list
        response_after = client.get("/activities")
        assert email not in response_after.json()[activity]["participants"]


class TestIntegration:
    """Integration tests for signup and unregister flow"""

    def test_signup_and_unregister_flow(self, client):
        """Test a complete signup and unregister flow"""
        email = "flow_test@mergington.edu"
        activity = "Music Ensemble"
        
        # Get initial participants count
        response = client.get("/activities")
        initial_count = len(response.json()[activity]["participants"])
        
        # Sign up
        signup_response = client.post(
            f"/activities/{quote(activity)}/signup?email={email}"
        )
        assert signup_response.status_code == 200
        
        # Verify participant was added
        response = client.get("/activities")
        mid_count = len(response.json()[activity]["participants"])
        assert mid_count == initial_count + 1
        
        # Unregister
        unregister_response = client.post(
            f"/activities/{quote(activity)}/unregister?email={email}"
        )
        assert unregister_response.status_code == 200
        
        # Verify participant was removed
        response = client.get("/activities")
        final_count = len(response.json()[activity]["participants"])
        assert final_count == initial_count

    def test_multiple_signups_and_unregisters(self, client):
        """Test multiple signups and unregisters in sequence"""
        activity = "Art Studio"
        emails = [f"artist{i}@mergington.edu" for i in range(3)]
        
        # Sign up all
        for email in emails:
            response = client.post(
                f"/activities/{quote(activity)}/signup?email={email}"
            )
            assert response.status_code == 200
        
        # Verify all are registered
        response = client.get("/activities")
        participants = response.json()[activity]["participants"]
        for email in emails:
            assert email in participants
        
        # Unregister all
        for email in emails:
            response = client.post(
                f"/activities/{quote(activity)}/unregister?email={email}"
            )
            assert response.status_code == 200
        
        # Verify all are unregistered
        response = client.get("/activities")
        participants = response.json()[activity]["participants"]
        for email in emails:
            assert email not in participants


class TestRootEndpoint:
    """Tests for the root endpoint"""

    def test_root_redirect(self, client):
        """Test that root endpoint redirects to static/index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert "/static/index.html" in response.headers["location"]
