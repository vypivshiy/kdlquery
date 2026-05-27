import pytest

from kdlquery import KdlDocument, KdlNode, parse


KDL_TEST_DOC = """\
/- kdl-version 2

app "my-service" version="1.0.0" {
    (network)server "primary" port=8080 tls=#true {
        host "localhost"
        host "127.0.0.1"
        timeout idle=30 connect=5
    }

    (network)server "replica" port=8081 tls=#false {
        host "replica.local"
        timeout idle=60 connect=5
    }

    router {
        route "GET" "/api/users" handler="users.list" auth=#true
        route "POST" "/api/users" handler="users.create" auth=#true
        route "GET" "/api/health" handler="health.check" auth=#false
        route "GET" "/static/*" handler="static.serve" auth=#false
    }

    plugins {
        plugin "auth" enabled=#true {
            (jwt)secret "hs256" key=(regex)"hs(256|512)"
            expires (i32)3600
        }
        plugin "cache" enabled=#true {
            backend "redis" host="cache.local" port=(u16)6379
        }
        plugin "debug" enabled=#false
    }

    (i32)workers 4
    (i32)timeout 30
    limits max-conn=(u32)1000 max-req=(u32)500
}
"""


@pytest.fixture()
def doc() -> KdlDocument:
    return parse(KDL_TEST_DOC)


def _names(results: list[KdlNode]) -> list[str]:
    return [n.name for n in results]


def _first_args(results: list[KdlNode]) -> list[object]:
    return [n.get_arg(0) for n in results]


def _node_reprs(results: list[KdlNode]) -> list[str]:
    parts: list[str] = []
    for n in results:
        r = n.name
        if n.args:
            r += f" {n.get_arg(0)!r}"
        parts.append(r)
    return parts


# ---------------------------------------------------------------------------
# Node by name and wildcard
# ---------------------------------------------------------------------------


class TestNodeSelector:
    def test_app(self, doc: KdlDocument) -> None:
        r = doc.select("app")
        assert _names(r) == ["app"]

    def test_server(self, doc: KdlDocument) -> None:
        r = doc.select("server")
        assert _first_args(r) == ["primary", "replica"]

    def test_wildcard_root(self, doc: KdlDocument) -> None:
        r = doc.select("*:root")
        assert _names(r) == ["app"]


# ---------------------------------------------------------------------------
# Type annotation on node
# ---------------------------------------------------------------------------


class TestTypeAnnotation:
    def test_network(self, doc: KdlDocument) -> None:
        r = doc.select("(network)")
        assert _names(r) == ["server", "server"]

    def test_network_server(self, doc: KdlDocument) -> None:
        r = doc.select("(network)server")
        assert _first_args(r) == ["primary", "replica"]

    def test_i32(self, doc: KdlDocument) -> None:
        r = doc.select("(i32)")
        assert _names(r) == ["workers", "timeout"]

    def test_i32_workers(self, doc: KdlDocument) -> None:
        r = doc.select("(i32)workers")
        assert _names(r) == ["workers"]

    def test_jwt(self, doc: KdlDocument) -> None:
        r = doc.select("(jwt)")
        assert _names(r) == ["secret"]

    def test_jwt_secret(self, doc: KdlDocument) -> None:
        r = doc.select("(jwt)secret")
        assert _first_args(r) == ["hs256"]


# ---------------------------------------------------------------------------
# Properties — basic
# ---------------------------------------------------------------------------


class TestPropertyBasic:
    def test_server_tls_exists(self, doc: KdlDocument) -> None:
        r = doc.select("server[tls]")
        assert _first_args(r) == ["primary", "replica"]

    def test_server_tls_true(self, doc: KdlDocument) -> None:
        r = doc.select("server[tls=#true]")
        assert _first_args(r) == ["primary"]

    def test_server_tls_false(self, doc: KdlDocument) -> None:
        r = doc.select("server[tls=#false]")
        assert _first_args(r) == ["replica"]

    def test_server_port_8080(self, doc: KdlDocument) -> None:
        r = doc.select("server[port=8080]")
        assert _first_args(r) == ["primary"]

    def test_route_auth_true(self, doc: KdlDocument) -> None:
        r = doc.select("route[auth=#true]")
        assert _first_args(r) == ["GET", "POST"]

    def test_route_handler_starts_users(self, doc: KdlDocument) -> None:
        r = doc.select('route[handler^="users"]')
        assert _first_args(r) == ["GET", "POST"]

    def test_route_handler_ends_check(self, doc: KdlDocument) -> None:
        r = doc.select('route[handler$="check"]')
        assert _first_args(r) == ["GET"]

    def test_route_handler_contains_serve(self, doc: KdlDocument) -> None:
        r = doc.select('route[handler~="serve"]')
        assert _first_args(r) == ["GET"]

    def test_app_version_exists(self, doc: KdlDocument) -> None:
        r = doc.select("app[version]")
        assert _names(r) == ["app"]

    def test_app_version_value(self, doc: KdlDocument) -> None:
        r = doc.select('app[version="1.0.0"]')
        assert _names(r) == ["app"]


# ---------------------------------------------------------------------------
# Properties — type annotation on value
# ---------------------------------------------------------------------------


class TestPropertyTypeAnnotation:
    def test_u16_port_any_node(self, doc: KdlDocument) -> None:
        r = doc.select("[(u16)port]")
        assert _names(r) == ["backend"]

    def test_backend_u16_port(self, doc: KdlDocument) -> None:
        r = doc.select("backend[(u16)port]")
        assert _names(r) == ["backend"]

    def test_backend_u16_port_value(self, doc: KdlDocument) -> None:
        r = doc.select("backend[(u16)port=6379]")
        assert _names(r) == ["backend"]

    def test_u32_max_conn_any(self, doc: KdlDocument) -> None:
        r = doc.select("[(u32)max-conn]")
        assert _names(r) == ["limits"]

    def test_limits_u32_max_conn(self, doc: KdlDocument) -> None:
        r = doc.select("limits[(u32)max-conn]")
        assert _names(r) == ["limits"]

    def test_limits_u32_max_conn_value(self, doc: KdlDocument) -> None:
        r = doc.select("limits[(u32)max-conn=1000]")
        assert _names(r) == ["limits"]

    def test_limits_u32_max_req_value(self, doc: KdlDocument) -> None:
        r = doc.select("limits[(u32)max-req=500]")
        assert _names(r) == ["limits"]

    def test_regex_key_any(self, doc: KdlDocument) -> None:
        r = doc.select("[(regex)key]")
        assert _names(r) == ["secret"]

    def test_secret_regex_key(self, doc: KdlDocument) -> None:
        r = doc.select("secret[(regex)key]")
        assert _names(r) == ["secret"]

    def test_secret_regex_key_contains(self, doc: KdlDocument) -> None:
        r = doc.select('secret[(regex)key~="hs"]')
        assert _names(r) == ["secret"]

    def test_wrong_type_backend_u32_port(self, doc: KdlDocument) -> None:
        r = doc.select("backend[(u32)port]")
        assert r == []

    def test_wrong_type_secret_jwt_key(self, doc: KdlDocument) -> None:
        r = doc.select("secret[(jwt)key]")
        assert r == []


# ---------------------------------------------------------------------------
# Arguments — basic
# ---------------------------------------------------------------------------


class TestArgumentBasic:
    def test_server_arg0_exists(self, doc: KdlDocument) -> None:
        r = doc.select("server[0]")
        assert _first_args(r) == ["primary", "replica"]

    def test_server_arg0_primary(self, doc: KdlDocument) -> None:
        r = doc.select('server[0="primary"]')
        assert _first_args(r) == ["primary"]

    def test_server_arg0_replica(self, doc: KdlDocument) -> None:
        r = doc.select('server[0="replica"]')
        assert _first_args(r) == ["replica"]

    def test_route_arg0_get(self, doc: KdlDocument) -> None:
        r = doc.select('route[0="GET"]')
        assert _first_args(r) == ["GET", "GET", "GET"]

    def test_route_arg1_api_users(self, doc: KdlDocument) -> None:
        r = doc.select('route[1="/api/users"]')
        assert _first_args(r) == ["GET", "POST"]

    def test_route_arg1_starts_api(self, doc: KdlDocument) -> None:
        r = doc.select('route[1^="/api"]')
        assert _first_args(r) == ["GET", "POST", "GET"]

    def test_route_arg1_starts_static(self, doc: KdlDocument) -> None:
        r = doc.select('route[1^="/static"]')
        assert _first_args(r) == ["GET"]

    def test_route_arg1_ends_users(self, doc: KdlDocument) -> None:
        r = doc.select('route[1$="/users"]')
        assert _first_args(r) == ["GET", "POST"]

    def test_route_arg1_contains_health(self, doc: KdlDocument) -> None:
        r = doc.select('route[1~="health"]')
        assert _first_args(r) == ["GET"]

    def test_route_any_arg_post(self, doc: KdlDocument) -> None:
        r = doc.select('route[*="POST"]')
        assert _first_args(r) == ["POST"]

    def test_plugin_arg0_exists(self, doc: KdlDocument) -> None:
        r = doc.select("plugin[0]")
        assert _first_args(r) == ["auth", "cache", "debug"]

    def test_plugin_arg1_exists(self, doc: KdlDocument) -> None:
        r = doc.select("plugin[1]")
        assert r == []


# ---------------------------------------------------------------------------
# Arguments — type annotation
# ---------------------------------------------------------------------------


class TestArgumentTypeAnnotation:
    def test_expires_i32_arg0_exists(self, doc: KdlDocument) -> None:
        r = doc.select("expires[(i32)0]")
        assert _names(r) == ["expires"]

    def test_expires_i32_arg0_value(self, doc: KdlDocument) -> None:
        r = doc.select("expires[(i32)0=3600]")
        assert _names(r) == ["expires"]

    def test_wrong_type_expires_u32(self, doc: KdlDocument) -> None:
        r = doc.select("expires[(u32)0]")
        assert r == []

    def test_i32_workers_i32_arg0(self, doc: KdlDocument) -> None:
        r = doc.select("(i32)workers[(i32)0]")
        assert r == []

    def test_wildcard_i32_arg0(self, doc: KdlDocument) -> None:
        r = doc.select("*[(i32)0]")
        assert _names(r) == ["expires"]


# ---------------------------------------------------------------------------
# Combinators
# ---------------------------------------------------------------------------


class TestCombinators:
    def test_child(self, doc: KdlDocument) -> None:
        r = doc.select("app > server")
        assert _first_args(r) == ["primary", "replica"]

    def test_nested_child(self, doc: KdlDocument) -> None:
        r = doc.select("app > router > route")
        assert _first_args(r) == ["GET", "POST", "GET", "GET"]

    def test_child_no_match(self, doc: KdlDocument) -> None:
        r = doc.select("app > route")
        assert r == []

    def test_plugins_child_plugin(self, doc: KdlDocument) -> None:
        r = doc.select("plugins > plugin")
        assert _first_args(r) == ["auth", "cache", "debug"]

    def test_plugin_child_backend(self, doc: KdlDocument) -> None:
        r = doc.select("plugin > backend")
        assert _names(r) == ["backend"]

    def test_typed_server_tls_true_child_host(self, doc: KdlDocument) -> None:
        r = doc.select("(network)server[tls=#true] > host")
        assert _first_args(r) == ["localhost", "127.0.0.1"]

    def test_typed_server_tls_false_child_host(self, doc: KdlDocument) -> None:
        r = doc.select("(network)server[tls=#false] > host")
        assert _first_args(r) == ["replica.local"]

    def test_descendant(self, doc: KdlDocument) -> None:
        r = doc.select("app server")
        assert _first_args(r) == ["primary", "replica"]

    def test_descendant_route(self, doc: KdlDocument) -> None:
        r = doc.select("app route")
        assert _first_args(r) == ["GET", "POST", "GET", "GET"]

    def test_descendant_plugin_backend(self, doc: KdlDocument) -> None:
        r = doc.select("plugins plugin[enabled=#true] > backend")
        assert _names(r) == ["backend"]


# ---------------------------------------------------------------------------
# Siblings
# ---------------------------------------------------------------------------


class TestSiblings:
    def test_adjacent_get_plus_route(self, doc: KdlDocument) -> None:
        r = doc.select('route[0="GET"] + route')
        assert _first_args(r) == ["POST", "GET"]

    def test_adjacent_post_plus_route(self, doc: KdlDocument) -> None:
        r = doc.select('route[0="POST"] + route')
        assert _first_args(r) == ["GET"]

    def test_general_get_tilde_route(self, doc: KdlDocument) -> None:
        r = doc.select('route[0="GET"][1$="/users"] ~ route')
        assert _first_args(r) == ["POST", "GET", "GET"]

    def test_adjacent_auth_plus_plugin(self, doc: KdlDocument) -> None:
        r = doc.select('plugin[0="auth"] + plugin')
        assert _first_args(r) == ["cache"]

    def test_general_auth_tilde_plugin(self, doc: KdlDocument) -> None:
        r = doc.select('plugin[0="auth"] ~ plugin')
        assert _first_args(r) == ["cache", "debug"]

    def test_adjacent_debug_plus_plugin(self, doc: KdlDocument) -> None:
        r = doc.select('plugin[0="debug"] + plugin')
        assert r == []


# ---------------------------------------------------------------------------
# Pseudo-classes
# ---------------------------------------------------------------------------


class TestPseudoClasses:
    def test_first_child(self, doc: KdlDocument) -> None:
        r = doc.select("route:first-child")
        assert _first_args(r) == ["GET"]

    def test_last_child(self, doc: KdlDocument) -> None:
        r = doc.select("route:last-child")
        assert _first_args(r) == ["GET"]

    def test_nth_child_2(self, doc: KdlDocument) -> None:
        r = doc.select("route:nth-child(2)")
        assert _first_args(r) == ["POST"]

    def test_nth_child_2n(self, doc: KdlDocument) -> None:
        r = doc.select("route:nth-child(2n)")
        assert _first_args(r) == ["POST", "GET"]

    def test_nth_child_2n_plus_1(self, doc: KdlDocument) -> None:
        r = doc.select("route:nth-child(2n+1)")
        assert _first_args(r) == ["GET", "GET"]

    def test_only_child_empty(self, doc: KdlDocument) -> None:
        r = doc.select("plugin:only-child")
        assert r == []

    def test_only_child_host(self, doc: KdlDocument) -> None:
        r = doc.select("host:only-child")
        assert _first_args(r) == ["replica.local"]

    def test_debug_last_child(self, doc: KdlDocument) -> None:
        r = doc.select('plugin[0="debug"]:last-child')
        assert _first_args(r) == ["debug"]

    def test_debug_empty(self, doc: KdlDocument) -> None:
        r = doc.select('plugin[0="debug"]:empty')
        assert _first_args(r) == ["debug"]

    def test_backend_empty(self, doc: KdlDocument) -> None:
        r = doc.select("backend:empty")
        assert _names(r) == ["backend"]

    def test_expires_empty(self, doc: KdlDocument) -> None:
        r = doc.select("expires:empty")
        assert _names(r) == ["expires"]

    def test_server_first_child(self, doc: KdlDocument) -> None:
        r = doc.select("server:first-child")
        assert _first_args(r) == ["primary"]

    def test_i32_last_child(self, doc: KdlDocument) -> None:
        r = doc.select("(i32):last-child")
        assert _names(r) == ["timeout"]

    def test_root_app(self, doc: KdlDocument) -> None:
        r = doc.select("app:root")
        assert _names(r) == ["app"]

    def test_root_server(self, doc: KdlDocument) -> None:
        r = doc.select("server:root")
        assert r == []


# ---------------------------------------------------------------------------
# Combined — regressions
# ---------------------------------------------------------------------------


class TestCombined:
    def test_type_prop_descendant(self, doc: KdlDocument) -> None:
        r = doc.select("(network)server[tls=#true] host")
        assert _first_args(r) == ["localhost", "127.0.0.1"]

    def test_child_wildcard_u32(self, doc: KdlDocument) -> None:
        r = doc.select("app > *[(u32)max-conn]")
        assert _names(r) == ["limits"]

    def test_wildcard_i32_arg_empty(self, doc: KdlDocument) -> None:
        r = doc.select("*[(i32)0]:empty")
        assert _names(r) == ["expires"]

    def test_multi_attr_filter(self, doc: KdlDocument) -> None:
        r = doc.select('route[auth=#false][0="GET"]')
        assert _first_args(r) == ["GET", "GET"]

    def test_jwt_secret_regex_key(self, doc: KdlDocument) -> None:
        r = doc.select("(jwt)secret[(regex)key]")
        assert _first_args(r) == ["hs256"]

    def test_descendant_plugin_u16_port_empty(self, doc: KdlDocument) -> None:
        r = doc.select("plugins plugin[(u16)port]")
        assert r == []

    def test_descendant_app_backend_u16(self, doc: KdlDocument) -> None:
        r = doc.select("app backend[(u16)port]")
        assert _names(r) == ["backend"]


# ---------------------------------------------------------------------------
# :not()
# ---------------------------------------------------------------------------


class TestNot:
    def test_server_not_tls(self, doc: KdlDocument) -> None:
        r = doc.select("server:not([tls])")
        assert r == []

    def test_server_not_port_8080(self, doc: KdlDocument) -> None:
        r = doc.select("server:not([port=8080])")
        assert _first_args(r) == ["replica"]

    def test_route_not_auth_true(self, doc: KdlDocument) -> None:
        r = doc.select("route:not([auth=#true])")
        assert _first_args(r) == ["GET", "GET"]

    def test_plugin_not_empty(self, doc: KdlDocument) -> None:
        r = doc.select("plugin:not(:empty)")
        assert _first_args(r) == ["auth", "cache"]

    def test_wildcard_not_app_root(self, doc: KdlDocument) -> None:
        r = doc.select("*:not(app):root")
        assert r == []

    def test_node_not_type_annotation(self, doc: KdlDocument) -> None:
        r = doc.select("*:not((i32))")
        names = _names(r)
        assert "workers" not in names
        # The (i32)timeout at app level is excluded, but timeout nodes under servers are included
        assert names.count("timeout") == 2  # the two non-typed timeouts under servers

    def test_not_combined_with_filter(self, doc: KdlDocument) -> None:
        r = doc.select('route:not([0="GET"])')
        assert _first_args(r) == ["POST"]


# ---------------------------------------------------------------------------
# :has()
# ---------------------------------------------------------------------------


class TestHas:
    def test_plugin_has_backend(self, doc: KdlDocument) -> None:
        r = doc.select("plugin:has(backend)")
        assert _first_args(r) == ["cache"]

    def test_server_has_host(self, doc: KdlDocument) -> None:
        r = doc.select("server:has(host)")
        assert _first_args(r) == ["primary", "replica"]

    def test_app_has_child_router(self, doc: KdlDocument) -> None:
        r = doc.select("app:has(> router)")
        assert _names(r) == ["app"]

    def test_plugin_has_child_secret(self, doc: KdlDocument) -> None:
        r = doc.select("plugin:has(> secret)")
        assert _first_args(r) == ["auth"]

    def test_plugin_has_child_secret_regex_key(self, doc: KdlDocument) -> None:
        r = doc.select("plugin:has(> secret[(regex)key])")
        assert _first_args(r) == ["auth"]

    def test_server_not_has_host(self, doc: KdlDocument) -> None:
        r = doc.select("server:not(:has(host))")
        assert r == []

    def test_app_has_descendant_backend(self, doc: KdlDocument) -> None:
        r = doc.select("app:has(backend)")
        assert _names(r) == ["app"]

    def test_plugin_has_child_expires(self, doc: KdlDocument) -> None:
        r = doc.select("plugin:has(> expires)")
        assert _first_args(r) == ["auth"]

    def test_server_has_timeout(self, doc: KdlDocument) -> None:
        r = doc.select("server:has(timeout)")
        assert _first_args(r) == ["primary", "replica"]

    def test_router_has_child_route_auth(self, doc: KdlDocument) -> None:
        r = doc.select("router:has(> route[auth=#true])")
        assert _names(r) == ["router"]


# ---------------------------------------------------------------------------
# Comma (union)
# ---------------------------------------------------------------------------


class TestComma:
    def test_two_names(self, doc: KdlDocument) -> None:
        r = doc.select("app, router")
        assert _names(r) == ["app", "router"]

    def test_three_names(self, doc: KdlDocument) -> None:
        r = doc.select("host, backend, expires")
        assert _names(r) == ["host", "host", "host", "expires", "backend"]

    def test_duplicate_dedup(self, doc: KdlDocument) -> None:
        r = doc.select("server, server")
        assert _first_args(r) == ["primary", "replica"]

    def test_overlapping_selectors(self, doc: KdlDocument) -> None:
        r = doc.select("server, (network)server")
        assert _first_args(r) == ["primary", "replica"]

    def test_filter_and_name(self, doc: KdlDocument) -> None:
        r = doc.select('app, route[0="POST"]')
        assert _names(r) == ["app", "route"]

    def test_complex_with_combinator(self, doc: KdlDocument) -> None:
        r = doc.select("app > server, app > router")
        names = _names(r)
        assert names == ["server", "server", "router"]

    def test_pseudo_and_filter(self, doc: KdlDocument) -> None:
        r = doc.select("*:root, backend:empty")
        assert _names(r) == ["app", "backend"]

    def test_not_and_has(self, doc: KdlDocument) -> None:
        r = doc.select("plugin:not(:empty), plugin:has(> secret)")
        assert _first_args(r) == ["auth", "cache"]


# ---------------------------------------------------------------------------
# select_one
# ---------------------------------------------------------------------------


class TestSelectOne:
    def test_returns_first(self, doc: KdlDocument) -> None:
        node = doc.select_one("server")
        assert node is not None
        assert node.get_arg(0) == "primary"

    def test_returns_none(self, doc: KdlDocument) -> None:
        assert doc.select_one("nonexistent") is None

    def test_root(self, doc: KdlDocument) -> None:
        node = doc.select_one("*:root")
        assert node is not None
        assert node.name == "app"

    def test_with_filter(self, doc: KdlDocument) -> None:
        node = doc.select_one("server[tls=#true]")
        assert node is not None
        assert node.get_arg(0) == "primary"

    def test_comma_returns_first_document_order(self, doc: KdlDocument) -> None:
        node = doc.select_one("backend, host")
        # host "localhost" comes before backend "redis" in document order
        assert node is not None
        assert node.name == "host"

    def test_descendant(self, doc: KdlDocument) -> None:
        node = doc.select_one("app > server > host")
        assert node is not None
        assert node.get_arg(0) == "localhost"

    def test_no_match_comma(self, doc: KdlDocument) -> None:
        assert doc.select_one("nonexist1, nonexist2") is None
