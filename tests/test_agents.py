"""Agent listing endpoints used by admins when assigning tickets."""


def emails(response):
    return {agent["email"] for agent in response.json()}


def test_agents_endpoint_lists_only_active_agents(
    client, admin_headers, agent_user, admin_user, requester_user,
    make_user, department, other_department,
):
    other_dept_agent = make_user(other_department, role="agent")
    make_user(department, role="agent", is_active=False)  # inactive agent -> excluded

    response = client.get("/agents", headers=admin_headers)

    assert response.status_code == 200
    # admin-only users and plain requesters are not agents
    assert emails(response) == {agent_user.email, other_dept_agent.email}


def test_department_agents_are_filtered_by_department(
    client, admin_headers, agent_user, department, other_department, make_user
):
    other_dept_agent = make_user(other_department, role="agent")

    it_agents = client.get(f"/departments/{department.id}/agents", headers=admin_headers)
    facilities_agents = client.get(f"/departments/{other_department.id}/agents", headers=admin_headers)

    assert emails(it_agents) == {agent_user.email}
    assert emails(facilities_agents) == {other_dept_agent.email}


def test_user_with_both_agent_and_admin_roles_is_listed_once(
    client, admin_headers, department, make_user
):
    both = make_user(department, role=["agent", "admin"])

    response = client.get("/agents", headers=admin_headers)

    assert [a["email"] for a in response.json()].count(both.email) == 1


def test_department_agents_for_unknown_department_returns_404(client, admin_headers):
    assert client.get("/departments/999999/agents", headers=admin_headers).status_code == 404


def test_agent_endpoints_require_admin(client, requester_headers, agent_headers, department):
    for headers in (requester_headers, agent_headers):
        assert client.get("/agents", headers=headers).status_code == 403
        assert client.get(f"/departments/{department.id}/agents", headers=headers).status_code == 403
    assert client.get("/agents").status_code == 401
