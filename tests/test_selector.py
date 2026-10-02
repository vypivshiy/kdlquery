import pytest

from kdlquery import KdlDocument, KdlNode, SelectorError, parse

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

    def test_not_comma_two_names(self, doc: KdlDocument) -> None:
        r = doc.select("app > *:not(server, router)")
        names = _names(r)
        assert "server" not in names
        assert "router" not in names

    def test_not_comma_with_pseudo(self, doc: KdlDocument) -> None:
        r = doc.select("plugin:not(:empty, [enabled=#false])")
        assert _first_args(r) == ["auth", "cache"]


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

    def test_has_comma_two_names(self, doc: KdlDocument) -> None:
        r = doc.select("server:has(host, timeout)")
        assert _first_args(r) == ["primary", "replica"]

    def test_has_comma_child_combinators(self, doc: KdlDocument) -> None:
        r = doc.select("app:has(> server, > router)")
        assert _names(r) == ["app"]

    def test_has_comma_mixed_combinators(self, doc: KdlDocument) -> None:
        r = doc.select("plugin:has(> secret, backend)")
        assert _first_args(r) == ["auth", "cache"]


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


# ---------------------------------------------------------------------------
# KdlNode.select / KdlNode.select_one
# ---------------------------------------------------------------------------


class TestKdlNodeSelect:
    def test_basic_descendant(self, doc: KdlDocument) -> None:
        app = doc.select_one("app")
        assert app is not None
        r = app.select("server")
        assert _first_args(r) == ["primary", "replica"]

    def test_deep_descendant(self, doc: KdlDocument) -> None:
        app = doc.select_one("app")
        assert app is not None
        r = app.select("host")
        assert _first_args(r) == ["localhost", "127.0.0.1", "replica.local"]

    def test_child_combinator(self, doc: KdlDocument) -> None:
        app = doc.select_one("app")
        assert app is not None
        r = app.select("server > host")
        assert _first_args(r) == ["localhost", "127.0.0.1", "replica.local"]

    def test_nested_child(self, doc: KdlDocument) -> None:
        app = doc.select_one("app")
        assert app is not None
        r = app.select("router > route")
        assert _first_args(r) == ["GET", "POST", "GET", "GET"]

    def test_type_annotation(self, doc: KdlDocument) -> None:
        app = doc.select_one("app")
        assert app is not None
        r = app.select("(network)server")
        assert _first_args(r) == ["primary", "replica"]

    def test_property_filter(self, doc: KdlDocument) -> None:
        app = doc.select_one("app")
        assert app is not None
        r = app.select("server[tls=#true]")
        assert _first_args(r) == ["primary"]

    def test_argument_filter(self, doc: KdlDocument) -> None:
        app = doc.select_one("app")
        assert app is not None
        r = app.select('route[0="POST"]')
        assert _first_args(r) == ["POST"]

    def test_first_child(self, doc: KdlDocument) -> None:
        router = doc.select_one("router")
        assert router is not None
        r = router.select("route:first-child")
        assert _first_args(r) == ["GET"]

    def test_last_child(self, doc: KdlDocument) -> None:
        router = doc.select_one("router")
        assert router is not None
        r = router.select("route:last-child")
        assert _first_args(r) == ["GET"]

    def test_nth_child(self, doc: KdlDocument) -> None:
        router = doc.select_one("router")
        assert router is not None
        r = router.select("route:nth-child(2)")
        assert _first_args(r) == ["POST"]

    def test_empty(self, doc: KdlDocument) -> None:
        debug = doc.select_one('plugin[0="debug"]')
        assert debug is not None
        r = debug.select("*:empty")
        assert r == []

    def test_only_child(self, doc: KdlDocument) -> None:
        server = doc.select_one('server[0="replica"]')
        assert server is not None
        r = server.select("host:only-child")
        assert _first_args(r) == ["replica.local"]

    def test_has(self, doc: KdlDocument) -> None:
        plugins = doc.select_one("plugins")
        assert plugins is not None
        r = plugins.select("plugin:has(> backend)")
        assert _first_args(r) == ["cache"]

    def test_not(self, doc: KdlDocument) -> None:
        router = doc.select_one("router")
        assert router is not None
        r = router.select("route:not([auth=#true])")
        assert _first_args(r) == ["GET", "GET"]

    def test_adjacent_sibling(self, doc: KdlDocument) -> None:
        router = doc.select_one("router")
        assert router is not None
        r = router.select('route[0="GET"] + route')
        assert _first_args(r) == ["POST", "GET"]

    def test_general_sibling(self, doc: KdlDocument) -> None:
        router = doc.select_one("router")
        assert router is not None
        r = router.select('route[0="POST"] ~ route')
        assert _first_args(r) == ["GET", "GET"]

    def test_root_never_matches(self, doc: KdlDocument) -> None:
        app = doc.select_one("app")
        assert app is not None
        r = app.select("*:root")
        assert r == []

    def test_wildcard_all_descendants(self, doc: KdlDocument) -> None:
        app = doc.select_one("app")
        assert app is not None
        r = app.select("*")
        assert app not in r
        assert len(r) > 0

    def test_empty_children(self, doc: KdlDocument) -> None:
        debug = doc.select_one('plugin[0="debug"]')
        assert debug is not None
        assert debug.select("*") == []

    def test_comma(self, doc: KdlDocument) -> None:
        app = doc.select_one("app")
        assert app is not None
        r = app.select("host, backend")
        assert _names(r) == ["host", "host", "host", "backend"]

    def test_select_one(self, doc: KdlDocument) -> None:
        app = doc.select_one("app")
        assert app is not None
        node = app.select_one("server")
        assert node is not None
        assert node.get_arg(0) == "primary"

    def test_select_one_none(self, doc: KdlDocument) -> None:
        debug = doc.select_one('plugin[0="debug"]')
        assert debug is not None
        assert debug.select_one("anything") is None

    def test_scoped_to_subtree(self, doc: KdlDocument) -> None:
        server = doc.select_one('server[0="primary"]')
        assert server is not None
        r = server.select("host")
        assert _first_args(r) == ["localhost", "127.0.0.1"]
        # Should not find hosts from other server
        assert "replica.local" not in _first_args(r)


# ---------------------------------------------------------------------------
# Quoted node selectors and descendant combinators (Ticket 01)
# ---------------------------------------------------------------------------

KDL_QUOTED_SELECTORS_DOC = """\
/- kdl-version 2

"service:web" "frontend" {
    "a>b" "ok" status="ok" {
        "child>item" "v1" {
            "deep+node" "leaf1"
        }
        "child_plain" "v2"
    }
    "c+d" "pending" status="pending" {
        "sub" "v3"
    }
    "x~y" "ok" status="ok"
    "a,b" "special" status="special"
    "a<b" "angle" status="angle"
    "spaced name" "val"
    "has'single" "single_quote"
    "has\\"double" "double_quote"
}

"service:api" "backend" {
    "c+d" "api_cd" status="api_cd"
    "isolated" "none"
}

"top>a" "sibling1"
"top+b" "sibling2"
"top~c" "sibling3"
"""


@pytest.fixture()
def qdoc() -> KdlDocument:
    return parse(KDL_QUOTED_SELECTORS_DOC)


class TestQuotedNodeSelectors:
    def test_double_and_single_quotes_exact_match(self, qdoc: KdlDocument) -> None:
        # Both "name" and 'name' match nodes with exact name
        r_double = qdoc.select('"service:web"')
        r_single = qdoc.select("'service:web'")
        assert _first_args(r_double) == ["frontend"]
        assert _first_args(r_single) == ["frontend"]

        r_double_api = qdoc.select('"service:api"')
        r_single_api = qdoc.select("'service:api'")
        assert _first_args(r_double_api) == ["backend"]
        assert _first_args(r_single_api) == ["backend"]

    def test_quoted_simple_node_name(self, doc: KdlDocument) -> None:
        # Standard unquoted identifiers also match when quoted
        assert _names(doc.select('"app"')) == ["app"]
        assert _names(doc.select("'app'")) == ["app"]
        assert _first_args(doc.select('"server"')) == ["primary", "replica"]
        assert _first_args(doc.select("'server'")) == ["primary", "replica"]

    def test_special_characters_in_node_names(self, qdoc: KdlDocument) -> None:
        # Combinator and list characters in node names don't trigger combinators
        assert _first_args(qdoc.select('"a>b"')) == ["ok"]
        assert _first_args(qdoc.select("'a>b'")) == ["ok"]

        assert _first_args(qdoc.select('"c+d"')) == ["pending", "api_cd"]
        assert _first_args(qdoc.select("'c+d'")) == ["pending", "api_cd"]

        assert _first_args(qdoc.select('"x~y"')) == ["ok"]
        assert _first_args(qdoc.select("'x~y'")) == ["ok"]

        assert _first_args(qdoc.select('"a,b"')) == ["special"]
        assert _first_args(qdoc.select("'a,b'")) == ["special"]

        assert _first_args(qdoc.select('"a<b"')) == ["angle"]
        assert _first_args(qdoc.select("'a<b'")) == ["angle"]

        assert _first_args(qdoc.select('"spaced name"')) == ["val"]
        assert _first_args(qdoc.select("'spaced name'")) == ["val"]

    def test_nested_quotes_in_node_names(self, qdoc: KdlDocument) -> None:
        # Single quote inside double quotes and double quote inside single quotes
        assert _first_args(qdoc.select('"has\'single"')) == ["single_quote"]
        assert _first_args(qdoc.select('\'has"double\'')) == ["double_quote"]

    def test_descendant_combinators_with_quotes(self, qdoc: KdlDocument, doc: KdlDocument) -> None:
        # Quoted ancestor and quoted descendant
        r1 = qdoc.select('"service:web" "child>item"')
        assert _first_args(r1) == ["v1"]
        r2 = qdoc.select("'service:web' 'child>item'")
        assert _first_args(r2) == ["v1"]

        # Quoted ancestor and unquoted descendant
        r3 = qdoc.select('"service:web" sub')
        assert _first_args(r3) == ["v3"]
        r4 = qdoc.select('"service:api" isolated')
        assert _first_args(r4) == ["none"]

        # Unquoted ancestor and quoted descendant
        r5 = doc.select('app "server"')
        assert _first_args(r5) == ["primary", "replica"]
        r6 = doc.select("app 'server'")
        assert _first_args(r6) == ["primary", "replica"]

        # Deep multi-step descendant chain
        r7 = qdoc.select('"service:web" "a>b" "deep+node"')
        assert _first_args(r7) == ["leaf1"]

    def test_child_combinator_with_quotes(self, qdoc: KdlDocument) -> None:
        # Direct child > with quotes
        assert _first_args(qdoc.select('"service:web" > "a>b"')) == ["ok"]
        assert _first_args(qdoc.select("'service:web' > 'a>b'")) == ["ok"]
        # Without whitespace around >
        assert _first_args(qdoc.select('"service:web">"a>b"')) == ["ok"]

        # Nested direct child
        assert _first_args(qdoc.select('"a>b" > "child>item"')) == ["v1"]
        assert _first_args(qdoc.select('"child>item" > "deep+node"')) == ["leaf1"]

        # Non-direct descendant fails with child combinator
        assert qdoc.select('"service:web" > "deep+node"') == []

    def test_adjacent_sibling_combinator_with_quotes(self, qdoc: KdlDocument) -> None:
        # Adjacent sibling +
        assert _first_args(qdoc.select('"a>b" + "c+d"')) == ["pending"]
        assert _first_args(qdoc.select("'a>b' + 'c+d'")) == ["pending"]
        assert _first_args(qdoc.select('"a>b"+"c+d"')) == ["pending"]

        assert _first_args(qdoc.select('"top>a" + "top+b"')) == ["sibling2"]

        # Non-adjacent sibling fails with adjacent combinator
        assert qdoc.select('"a>b" + "x~y"') == []

    def test_general_sibling_combinator_with_quotes(self, qdoc: KdlDocument) -> None:
        # General sibling ~
        assert _first_args(qdoc.select('"a>b" ~ "x~y"')) == ["ok"]
        assert _first_args(qdoc.select("'a>b' ~ 'x~y'")) == ["ok"]
        assert _first_args(qdoc.select('"a>b"~"x~y"')) == ["ok"]

        assert _first_args(qdoc.select('"top>a" ~ "top~c"')) == ["sibling3"]

        # Reverse order does not match
        assert qdoc.select('"x~y" ~ "a>b"') == []

    def test_mixed_combinators_with_quotes(self, qdoc: KdlDocument) -> None:
        r1 = qdoc.select('"service:web" > "a>b" > "child>item" > "deep+node"')
        assert _first_args(r1) == ["leaf1"]

        r2 = qdoc.select('"service:web" > "a>b" + "c+d" > sub')
        assert _first_args(r2) == ["v3"]

    def test_selector_list_with_quotes(self, qdoc: KdlDocument) -> None:
        # Comma list with string-wrapped node selectors
        r1 = qdoc.select('"a>b", "x~y"')
        assert _first_args(r1) == ["ok", "ok"]
        assert _names(r1) == ["a>b", "x~y"]

        r2 = qdoc.select("'top>a', 'top+b'")
        assert _names(r2) == ["top>a", "top+b"]

        # Comma INSIDE quoted node name matches exact node, not list
        r3 = qdoc.select('"a,b"')
        assert _names(r3) == ["a,b"]
        assert _first_args(r3) == ["special"]

    def test_pseudo_class_not_with_quotes(self, qdoc: KdlDocument) -> None:
        # :not with string-wrapped node selector
        r1 = qdoc.select('"service:web":not("service:api")')
        assert _first_args(r1) == ["frontend"]

        r2 = qdoc.select('"service:api":not("service:api")')
        assert r2 == []

        r3 = qdoc.select('"service:web" > *:not("a>b", "c+d")')
        assert "a>b" not in _names(r3)
        assert "c+d" not in _names(r3)
        assert "x~y" in _names(r3)

    def test_pseudo_class_has_with_quotes(self, qdoc: KdlDocument) -> None:
        # :has with quoted descendant
        r1 = qdoc.select('"service:web":has("child>item")')
        assert _first_args(r1) == ["frontend"]
        r1_single = qdoc.select("'service:web':has('child>item')")
        assert _first_args(r1_single) == ["frontend"]

        # :has with explicit child combinator
        r2 = qdoc.select('"service:web":has(> "a>b")')
        assert _first_args(r2) == ["frontend"]

        # :has with non-direct child fails when > is used
        r3 = qdoc.select('"service:web":has(> "child>item")')
        assert r3 == []

        # :has deep match
        r4 = qdoc.select('"a>b":has("deep+node")')
        assert _first_args(r4) == ["ok"]

        # :has non-matching selector
        assert qdoc.select('"service:web":has("nonexistent")') == []

    def test_public_api_select_one(self, qdoc: KdlDocument) -> None:
        # KdlDocument.select_one() with double and single quotes
        node1 = qdoc.select_one('"service:web"')
        assert node1 is not None
        assert node1.name == "service:web"

        node2 = qdoc.select_one("'a>b'")
        assert node2 is not None
        assert node2.name == "a>b"

        assert qdoc.select_one('"nonexistent"') is None
        assert qdoc.select_one("'nonexistent'") is None

    def test_public_api_node_select_and_select_one(self, qdoc: KdlDocument) -> None:
        # KdlNode.select() and KdlNode.select_one() with string-wrapped node selectors
        web = qdoc.select_one('"service:web"')
        assert web is not None

        # Subtree select
        r = web.select('"a>b"')
        assert len(r) == 1
        assert r[0].name == "a>b"

        # Subtree select with single quote
        r_single = web.select("'c+d'")
        assert len(r_single) == 1
        assert r_single[0].get_arg(0) == "pending"

        # Subtree select_one
        child = web.select_one('"child>item"')
        assert child is not None
        assert child.name == "child>item"
        assert web.select_one('"nonexistent"') is None

        # Combinators within subtree
        deep = web.select('"a>b" > "child>item"')
        assert len(deep) == 1
        assert deep[0].name == "child>item"

    def test_public_api_node_matches(self, qdoc: KdlDocument) -> None:
        # KdlNode.matches() with double and single quotes
        web = qdoc.select_one('"service:web"')
        assert web is not None

        assert web.matches('"service:web"')
        assert web.matches("'service:web'")
        assert not web.matches('"service:api"')
        assert not web.matches("'service:api'")

        # Matches with pseudo-classes
        assert web.matches(':not("service:api")')
        assert not web.matches(':not("service:web")')
        assert web.matches(':has("child>item")')
        assert not web.matches(':has("nonexistent")')

        # Child node matching
        ab = qdoc.select_one('"a>b"')
        assert ab is not None
        assert ab.matches('"a>b"')
        assert ab.matches("'a>b'")
        assert not ab.matches('"c+d"')
        assert ab.matches('"service:web" > "a>b"')
        assert not ab.matches('"service:api" > "a>b"')

    def test_unterminated_quotes_raise_selector_error(self, qdoc: KdlDocument) -> None:
        web = qdoc.select_one('"service:web"')
        assert web is not None

        # Unterminated double quotes
        with pytest.raises(SelectorError, match="Unterminated string"):
            qdoc.select('"unterminated')

        with pytest.raises(SelectorError, match="Unterminated string"):
            qdoc.select('parent "unterminated')

        with pytest.raises(SelectorError, match="Unterminated string"):
            qdoc.select(':not("unterminated)')

        with pytest.raises(SelectorError, match="Unterminated string"):
            qdoc.select(':has("unterminated)')

        with pytest.raises(SelectorError, match="Unterminated string"):
            qdoc.select_one('"unterminated')

        with pytest.raises(SelectorError, match="Unterminated string"):
            web.select('"unterminated')

        with pytest.raises(SelectorError, match="Unterminated string"):
            web.select_one('"unterminated')

        with pytest.raises(SelectorError, match="Unterminated string"):
            web.matches('"unterminated')

        # Unterminated single quotes
        with pytest.raises(SelectorError, match="Unterminated string"):
            qdoc.select("'unterminated")

        with pytest.raises(SelectorError, match="Unterminated string"):
            qdoc.select("parent 'unterminated")

        with pytest.raises(SelectorError, match="Unterminated string"):
            qdoc.select(":not('unterminated)")

        with pytest.raises(SelectorError, match="Unterminated string"):
            qdoc.select(":has('unterminated)")

        with pytest.raises(SelectorError, match="Unterminated string"):
            qdoc.select_one("'unterminated")

        with pytest.raises(SelectorError, match="Unterminated string"):
            web.select("'unterminated")

        with pytest.raises(SelectorError, match="Unterminated string"):
            web.select_one("'unterminated")

        with pytest.raises(SelectorError, match="Unterminated string"):
            web.matches("'unterminated")

        # Escaped closing quote resulting in unterminated string
        with pytest.raises(SelectorError, match="Unterminated string"):
            qdoc.select('"escaped\\"')

        with pytest.raises(SelectorError, match="Unterminated string"):
            qdoc.select("'escaped\\'")


# ---------------------------------------------------------------------------
# Backslash-escaped identifiers (Ticket 02)
# ---------------------------------------------------------------------------

KDL_ESCAPED_DOC = r"""/- kdl-version 2

"a>b" 10 key="val1" {
    "c+d" 20 {
        "nested:item" 21
    }
    "e~f" 30
    "g,h" 40
}

">foo" 50
"+bar" 60
"~baz" 70
",qux" 80
"ns:service" 90 active=#true {
    "leaf" 91
}
"complex>a+b~c,d:e" 100
"has\\backslash" 110
"has\"quote" 120
"end>" 130
"hello world" 140
"""


@pytest.fixture()
def escaped_doc() -> KdlDocument:
    return parse(KDL_ESCAPED_DOC)


class TestEscapedIdentifiersBasic:
    def test_escaped_gt(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"a\>b")
        assert _names(r) == ["a>b"]
        assert _first_args(r) == [10]

    def test_escaped_gt_at_start(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"\>foo")
        assert _names(r) == [">foo"]
        assert _first_args(r) == [50]

    def test_escaped_gt_at_end(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"end\>")
        assert _names(r) == ["end>"]
        assert _first_args(r) == [130]

    def test_escaped_plus(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"c\+d")
        assert _names(r) == ["c+d"]
        assert _first_args(r) == [20]

    def test_escaped_plus_at_start(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"\+bar")
        assert _names(r) == ["+bar"]
        assert _first_args(r) == [60]

    def test_escaped_tilde(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"e\~f")
        assert _names(r) == ["e~f"]
        assert _first_args(r) == [30]

    def test_escaped_tilde_at_start(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"\~baz")
        assert _names(r) == ["~baz"]
        assert _first_args(r) == [70]

    def test_escaped_comma(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"g\,h")
        assert _names(r) == ["g,h"]
        assert _first_args(r) == [40]

    def test_escaped_comma_at_start(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"\,qux")
        assert _names(r) == [",qux"]
        assert _first_args(r) == [80]

    def test_escaped_colon(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"ns\:service")
        assert _names(r) == ["ns:service"]
        assert _first_args(r) == [90]

    def test_escaped_multiple_in_one_ident(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"complex\>a\+b\~c\,d\:e")
        assert _names(r) == ["complex>a+b~c,d:e"]
        assert _first_args(r) == [100]

    def test_escaped_backslash(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"has\\backslash")
        assert _names(r) == [r"has\backslash"]
        assert _first_args(r) == [110]

    def test_escaped_quote(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"has\"quote")
        assert _names(r) == ['has"quote']
        assert _first_args(r) == [120]

    def test_escaped_space(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"hello\ world")
        assert _names(r) == ["hello world"]
        assert _first_args(r) == [140]

    def test_escaped_with_attribute_filter(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r'a\>b[key="val1"]')
        assert _names(r) == ["a>b"]
        r2 = escaped_doc.select(r"a\>b[0=10]")
        assert _names(r2) == ["a>b"]

    def test_unterminated_escape_at_eof(self, escaped_doc: KdlDocument) -> None:
        with pytest.raises(SelectorError, match="Unterminated escape sequence"):
            escaped_doc.select("foo\\")

    def test_unterminated_escape_single_backslash(
        self, escaped_doc: KdlDocument
    ) -> None:
        with pytest.raises(SelectorError, match="Unterminated escape sequence"):
            escaped_doc.select("\\")


class TestEscapedIdentifiersCombinators:
    def test_child_combinator(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"a\>b > c\+d")
        assert _names(r) == ["c+d"]
        assert _first_args(r) == [20]

    def test_child_combinator_without_whitespace(
        self, escaped_doc: KdlDocument
    ) -> None:
        r = escaped_doc.select(r"a\>b>c\+d")
        assert _names(r) == ["c+d"]
        assert _first_args(r) == [20]

    def test_nested_child_combinators(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"a\>b > c\+d > nested\:item")
        assert _names(r) == ["nested:item"]
        assert _first_args(r) == [21]

    def test_descendant_combinator(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"a\>b nested\:item")
        assert _names(r) == ["nested:item"]
        assert _first_args(r) == [21]

    def test_adjacent_sibling(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"c\+d + e\~f")
        assert _names(r) == ["e~f"]
        assert _first_args(r) == [30]

    def test_adjacent_sibling_without_whitespace(
        self, escaped_doc: KdlDocument
    ) -> None:
        r = escaped_doc.select(r"c\+d+e\~f")
        assert _names(r) == ["e~f"]
        assert _first_args(r) == [30]

    def test_general_sibling(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"c\+d ~ g\,h")
        assert _names(r) == ["g,h"]
        assert _first_args(r) == [40]

    def test_general_sibling_without_whitespace(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"c\+d~g\,h")
        assert _names(r) == ["g,h"]
        assert _first_args(r) == [40]

    def test_chained_child_and_general_sibling(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"a\>b > c\+d ~ g\,h")
        assert _names(r) == ["g,h"]


class TestEscapedIdentifiersPseudoClasses:
    def test_not_with_escaped_node(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"a\>b > *:not(c\+d)")
        assert _names(r) == ["e~f", "g,h"]

    def test_not_with_multiple_escaped_nodes(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"a\>b > *:not(c\+d, e\~f)")
        assert _names(r) == ["g,h"]

    def test_escaped_node_with_not(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"a\>b:not(:empty)")
        assert _names(r) == ["a>b"]

    def test_has_descendant(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"a\>b:has(nested\:item)")
        assert _names(r) == ["a>b"]

    def test_has_child(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"a\>b:has(> c\+d)")
        assert _names(r) == ["a>b"]

    def test_has_nested_child(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"c\+d:has(> nested\:item)")
        assert _names(r) == ["c+d"]
        r2 = escaped_doc.select(r"a\>b:has(> e\~f)")
        assert _names(r2) == ["a>b"]

    def test_first_child(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"c\+d:first-child")
        assert _names(r) == ["c+d"]

    def test_last_child(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"g\,h:last-child")
        assert _names(r) == ["g,h"]


class TestEscapedIdentifiersCommaList:
    def test_comma_union_of_escaped_nodes(self, escaped_doc: KdlDocument) -> None:
        r = escaped_doc.select(r"a\>b, \>foo, \+bar")
        assert _names(r) == ["a>b", ">foo", "+bar"]

    def test_escaped_comma_within_node_in_comma_union(
        self, escaped_doc: KdlDocument
    ) -> None:
        r = escaped_doc.select(r"g\,h, a\>b")
        assert _names(r) == ["a>b", "g,h"]


class TestEscapedIdentifiersSelectOne:
    def test_select_one_found(self, escaped_doc: KdlDocument) -> None:
        node = escaped_doc.select_one(r"a\>b > c\+d")
        assert node is not None
        assert node.name == "c+d"
        assert node.get_arg(0) == 20

    def test_select_one_none(self, escaped_doc: KdlDocument) -> None:
        node = escaped_doc.select_one(r"non\>existent")
        assert node is None


class TestEscapedIdentifiersKdlNodeMethods:
    def test_kdl_node_matches(self, escaped_doc: KdlDocument) -> None:
        node = escaped_doc.select_one(r"a\>b")
        assert node is not None
        assert node.matches(r"a\>b") is True
        assert node.matches(r"c\+d") is False
        assert node.matches(r":has(c\+d)") is True
        assert node.matches(r":has(> c\+d)") is True
        assert node.matches(r":not(a\>b)") is False
        assert node.matches(r":not(c\+d)") is True

    def test_kdl_node_matches_start_escaped(self, escaped_doc: KdlDocument) -> None:
        node = escaped_doc.select_one(r"\>foo")
        assert node is not None
        assert node.matches(r"\>foo") is True
        assert node.matches(r"\+bar") is False

    def test_kdl_node_select(self, escaped_doc: KdlDocument) -> None:
        node = escaped_doc.select_one(r"a\>b")
        assert node is not None
        r = node.select(r"c\+d")
        assert _names(r) == ["c+d"]
        r2 = node.select(r"c\+d > nested\:item")
        assert _names(r2) == ["nested:item"]

    def test_kdl_node_select_one(self, escaped_doc: KdlDocument) -> None:
        node = escaped_doc.select_one(r"a\>b")
        assert node is not None
        item = node.select_one(r"nested\:item")
        assert item is not None
        assert item.name == "nested:item"
        assert item.get_arg(0) == 21
        assert node.select_one(r"non\>existent") is None


# ---------------------------------------------------------------------------
# Disambiguated type annotations (Ticket 03)
# ---------------------------------------------------------------------------

KDL_TYPED_DOC = r"""/- kdl-version 2

("my/custom:type")service "srv_quoted" port=("u:16")8080 active=#true {
    ("child/nested:type")worker "w1"
    (nested:type2)worker "w2"
}

(custom:v1)service "srv_unquoted" port=(u:16)8081 active=#false {
    ("child/nested:type")worker "w3"
}

("ns:type")app "app1" ("u:16")100 (custom:v1)200 {
    (custom:v1)setting "s1"
}

("a>b")node_gt "gt_node"
("a+b")node_plus "plus_node"
("a~b")node_tilde "tilde_node"
("a,b")node_comma "comma_node"
("spaced type")node_space "space_node"

untyped_node "no_type" port=8082
"""


@pytest.fixture()
def typed_doc() -> KdlDocument:
    return parse(KDL_TYPED_DOC)


class TestDisambiguatedTypeAnnotationsQuoted:
    def test_double_quoted_type_on_node(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select('("my/custom:type")service')
        assert _first_args(r) == ["srv_quoted"]

    def test_double_quoted_type_without_node_name(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select('("my/custom:type")')
        assert _first_args(r) == ["srv_quoted"]

    def test_double_quoted_type_with_wildcard(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select('("my/custom:type")*')
        assert _first_args(r) == ["srv_quoted"]

    def test_double_quoted_type_matching_unquoted_kdl(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select('("custom:v1")service')
        assert _first_args(r) == ["srv_unquoted"]

    def test_double_quoted_special_characters_in_type(self, typed_doc: KdlDocument) -> None:
        assert _first_args(typed_doc.select('("a>b")node_gt')) == ["gt_node"]
        assert _first_args(typed_doc.select('("a+b")node_plus')) == ["plus_node"]
        assert _first_args(typed_doc.select('("a~b")node_tilde')) == ["tilde_node"]
        assert _first_args(typed_doc.select('("a,b")node_comma')) == ["comma_node"]
        assert _first_args(typed_doc.select('("spaced type")node_space')) == ["space_node"]

    def test_single_quoted_type_on_node(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select("('my/custom:type')service")
        assert _first_args(r) == ["srv_quoted"]

    def test_single_quoted_type_without_node_name(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select("('my/custom:type')")
        assert _first_args(r) == ["srv_quoted"]

    def test_single_quoted_type_with_wildcard(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select("('my/custom:type')*")
        assert _first_args(r) == ["srv_quoted"]

    def test_single_quoted_type_matching_unquoted_kdl(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select("('custom:v1')service")
        assert _first_args(r) == ["srv_unquoted"]

    def test_single_quoted_special_characters_in_type(self, typed_doc: KdlDocument) -> None:
        assert _first_args(typed_doc.select("('a>b')node_gt")) == ["gt_node"]
        assert _first_args(typed_doc.select("('spaced type')node_space")) == ["space_node"]


class TestDisambiguatedTypeAnnotationsEscaped:
    def test_escaped_type_matching_quoted_kdl(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select(r"(my\/custom\:type)service")
        assert _first_args(r) == ["srv_quoted"]

    def test_escaped_type_without_node_name(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select(r"(my\/custom\:type)")
        assert _first_args(r) == ["srv_quoted"]

    def test_escaped_type_with_wildcard(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select(r"(my\/custom\:type)*")
        assert _first_args(r) == ["srv_quoted"]

    def test_escaped_type_matching_unquoted_kdl(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select(r"(custom\:v1)service")
        assert _first_args(r) == ["srv_unquoted"]

    def test_escaped_special_characters_in_type(self, typed_doc: KdlDocument) -> None:
        assert _first_args(typed_doc.select(r"(a\>b)node_gt")) == ["gt_node"]
        assert _first_args(typed_doc.select(r"(a\+b)node_plus")) == ["plus_node"]
        assert _first_args(typed_doc.select(r"(a\~b)node_tilde")) == ["tilde_node"]
        assert _first_args(typed_doc.select(r"(a\,b)node_comma")) == ["comma_node"]
        assert _first_args(typed_doc.select(r"(spaced\ type)node_space")) == ["space_node"]


class TestDisambiguatedTypeAnnotationsInFilters:
    def test_property_type_double_quoted(self, typed_doc: KdlDocument) -> None:
        # Match quoted KDL property type
        r1 = typed_doc.select('service[("u:16")port=8080]')
        assert _first_args(r1) == ["srv_quoted"]

        # Match unquoted KDL property type
        r2 = typed_doc.select('service[("u:16")port=8081]')
        assert _first_args(r2) == ["srv_unquoted"]

        # Existence filter with type annotation
        r3 = typed_doc.select('service[("u:16")port]')
        assert _first_args(r3) == ["srv_quoted", "srv_unquoted"]

    def test_property_type_single_quoted(self, typed_doc: KdlDocument) -> None:
        r1 = typed_doc.select("service[('u:16')port=8080]")
        assert _first_args(r1) == ["srv_quoted"]

        r2 = typed_doc.select("service[('u:16')port=8081]")
        assert _first_args(r2) == ["srv_unquoted"]

        r3 = typed_doc.select("service[('u:16')port]")
        assert _first_args(r3) == ["srv_quoted", "srv_unquoted"]

    def test_property_type_backslash_escaped(self, typed_doc: KdlDocument) -> None:
        r1 = typed_doc.select(r"service[(u\:16)port=8080]")
        assert _first_args(r1) == ["srv_quoted"]

        r2 = typed_doc.select(r"service[(u\:16)port=8081]")
        assert _first_args(r2) == ["srv_unquoted"]

        r3 = typed_doc.select(r"service[(u\:16)port]")
        assert _first_args(r3) == ["srv_quoted", "srv_unquoted"]

    def test_property_type_mismatch_returns_empty(self, typed_doc: KdlDocument) -> None:
        assert typed_doc.select('service[("i32")port]') == []
        assert typed_doc.select('untyped_node[("u:16")port]') == []

    def test_argument_type_double_quoted(self, typed_doc: KdlDocument) -> None:
        # Match quoted argument type
        r1 = typed_doc.select('app[("u:16")1=100]')
        assert _first_args(r1) == ["app1"]

        # Match unquoted argument type
        r2 = typed_doc.select('app[("custom:v1")2=200]')
        assert _first_args(r2) == ["app1"]

        # Argument type existence check
        r3 = typed_doc.select('app[("u:16")1]')
        assert _first_args(r3) == ["app1"]

    def test_argument_type_single_quoted(self, typed_doc: KdlDocument) -> None:
        r1 = typed_doc.select("app[('u:16')1=100]")
        assert _first_args(r1) == ["app1"]

        r2 = typed_doc.select("app[('custom:v1')2=200]")
        assert _first_args(r2) == ["app1"]

    def test_argument_type_backslash_escaped(self, typed_doc: KdlDocument) -> None:
        r1 = typed_doc.select(r"app[(u\:16)1=100]")
        assert _first_args(r1) == ["app1"]

        r2 = typed_doc.select(r"app[(custom\:v1)2=200]")
        assert _first_args(r2) == ["app1"]

        r3 = typed_doc.select(r"app[(u\:16)1]")
        assert _first_args(r3) == ["app1"]

    def test_argument_type_mismatch_returns_empty(self, typed_doc: KdlDocument) -> None:
        assert typed_doc.select('app[("i32")1=100]') == []


class TestDisambiguatedTypeAnnotationsCombinators:
    def test_descendant_combinator_with_types(self, typed_doc: KdlDocument) -> None:
        r1 = typed_doc.select('("my/custom:type")service ("child/nested:type")worker')
        assert _first_args(r1) == ["w1"]

        r2 = typed_doc.select(r'(my\/custom\:type)service (nested\:type2)worker')
        assert _first_args(r2) == ["w2"]

        r3 = typed_doc.select('service ("child/nested:type")worker')
        assert _first_args(r3) == ["w1", "w3"]

    def test_child_combinator_with_types(self, typed_doc: KdlDocument) -> None:
        r1 = typed_doc.select('("my/custom:type")service > ("child/nested:type")worker')
        assert _first_args(r1) == ["w1"]

        r2 = typed_doc.select(r'(my\/custom\:type)service > (nested\:type2)worker')
        assert _first_args(r2) == ["w2"]

        # Without whitespace
        r3 = typed_doc.select('("my/custom:type")service>("child/nested:type")worker')
        assert _first_args(r3) == ["w1"]

    def test_adjacent_sibling_combinator_with_types(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select(r'("child/nested:type")worker + (nested\:type2)worker')
        assert _first_args(r) == ["w2"]

    def test_general_sibling_combinator_with_types(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select('("a>b")node_gt ~ ("a,b")node_comma')
        assert _first_args(r) == ["comma_node"]

    def test_typed_node_and_typed_filter_with_child_combinator(
        self, typed_doc: KdlDocument
    ) -> None:
        r = typed_doc.select(
            '("my/custom:type")service[("u:16")port=8080] > ("child/nested:type")worker'
        )
        assert _first_args(r) == ["w1"]

    def test_comma_union_with_types(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select(r'("my/custom:type")service, (custom\:v1)service')
        assert _first_args(r) == ["srv_quoted", "srv_unquoted"]


class TestDisambiguatedTypeAnnotationsPseudoClasses:
    def test_not_with_quoted_type(self, typed_doc: KdlDocument) -> None:
        r1 = typed_doc.select('service > *:not(("child/nested:type"))')
        assert _first_args(r1) == ["w2"]

        r2 = typed_doc.select(r"service > *:not((child\/nested\:type))")
        assert _first_args(r2) == ["w2"]

        r3 = typed_doc.select("service > *:not(('child/nested:type'))")
        assert _first_args(r3) == ["w2"]

    def test_not_on_typed_node(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select('service:not(("custom:v1"))')
        assert _first_args(r) == ["srv_quoted"]

    def test_has_with_quoted_type(self, typed_doc: KdlDocument) -> None:
        r1 = typed_doc.select('service:has(("child/nested:type")worker)')
        assert _first_args(r1) == ["srv_quoted", "srv_unquoted"]

        r2 = typed_doc.select(r"service:has(> (nested\:type2)worker)")
        assert _first_args(r2) == ["srv_quoted"]

        r3 = typed_doc.select(r"service:has(> (custom\:v1)setting)")
        assert r3 == []

    def test_first_child_with_type(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select('("child/nested:type")worker:first-child')
        assert _first_args(r) == ["w1", "w3"]

    def test_last_child_with_type(self, typed_doc: KdlDocument) -> None:
        r = typed_doc.select(r"(nested\:type2)worker:last-child")
        assert _first_args(r) == ["w2"]


class TestDisambiguatedTypeAnnotationsPublicAPIs:
    def test_select_one_with_types(self, typed_doc: KdlDocument) -> None:
        node1 = typed_doc.select_one('("my/custom:type")service')
        assert node1 is not None
        assert node1.get_arg(0) == "srv_quoted"

        node2 = typed_doc.select_one(r"(custom\:v1)service")
        assert node2 is not None
        assert node2.get_arg(0) == "srv_unquoted"

        assert typed_doc.select_one('("nonexistent:type")service') is None

    def test_kdl_node_select_and_select_one_with_types(self, typed_doc: KdlDocument) -> None:
        srv = typed_doc.select_one('("my/custom:type")service')
        assert srv is not None

        # Subtree select
        r1 = srv.select('("child/nested:type")worker')
        assert _first_args(r1) == ["w1"]

        r2 = srv.select(r"(nested\:type2)worker")
        assert _first_args(r2) == ["w2"]

        # Subtree select_one
        w1 = srv.select_one('("child/nested:type")worker')
        assert w1 is not None
        assert w1.get_arg(0) == "w1"

        assert srv.select_one('("nonexistent:type")') is None

    def test_kdl_node_matches_with_types(self, typed_doc: KdlDocument) -> None:
        srv = typed_doc.select_one('("my/custom:type")service')
        assert srv is not None

        # Matches type annotation variations
        assert srv.matches('("my/custom:type")service') is True
        assert srv.matches(r"(my\/custom\:type)service") is True
        assert srv.matches("('my/custom:type')service") is True
        assert srv.matches('("my/custom:type")') is True
        assert srv.matches('("custom:v1")service') is False

        # Matches property filter with type annotation
        assert srv.matches('[("u:16")port=8080]') is True
        assert srv.matches(r"[(u\:16)port=8080]") is True
        assert srv.matches("[('u:16')port=8080]") is True
        assert srv.matches('[("u:16")port=9999]') is False
        assert srv.matches('[("i32")port=8080]') is False

        # Matches pseudo-classes with types
        assert srv.matches(':has(("child/nested:type")worker)') is True
        assert srv.matches(':not(("custom:v1")service)') is True
        assert srv.matches(':not(("my/custom:type")service)') is False

    def test_synthetic_node_matching(self) -> None:
        # Node created with unparenthesized type annotation
        n1 = KdlNode.create("item", type_annotation="my/type")
        assert n1.matches('("my/type")item') is True
        assert n1.matches(r"(my\/type)item") is True
        assert n1.matches("('my/type')item") is True
        assert n1.matches('("other/type")item') is False

        # Node created with parenthesized type annotation
        n2 = KdlNode.create("item", type_annotation="(my/type)")
        assert n2.matches('("my/type")item') is True
        assert n2.matches(r"(my\/type)item") is True
        assert n2.matches("('my/type')item") is True

        # Node created with quoted parenthesized type annotation
        n3 = KdlNode.create("item", type_annotation='("my/type")')
        assert n3.matches('("my/type")item') is True
        assert n3.matches(r"(my\/type)item") is True


class TestDisambiguatedTypeAnnotationsErrors:
    def test_unterminated_string_in_type_annotation(self, typed_doc: KdlDocument) -> None:
        with pytest.raises(SelectorError, match="Unterminated string"):
            typed_doc.select('("unterminated)node')

        with pytest.raises(SelectorError, match="Unterminated string"):
            typed_doc.select("('unterminated)node")

        with pytest.raises(SelectorError, match="Unterminated string"):
            typed_doc.select('node[("unterminated)port=8080]')

    def test_unterminated_escape_in_type_annotation(self, typed_doc: KdlDocument) -> None:
        with pytest.raises(SelectorError, match="Unterminated escape sequence"):
            typed_doc.select("(foo\\")

        with pytest.raises(SelectorError, match="Unterminated escape sequence"):
            typed_doc.select("node[(foo\\")

    def test_escaped_closing_paren_in_type_annotation_missing_rparen(
        self, typed_doc: KdlDocument
    ) -> None:
        with pytest.raises(SelectorError, match="Expected RPAREN"):
            typed_doc.select(r"(unterminated\)node")

    def test_empty_type_annotation_raises_selector_error(self, typed_doc: KdlDocument) -> None:
        with pytest.raises(SelectorError, match="Expected type annotation identifier or string"):
            typed_doc.select("()node")

        with pytest.raises(SelectorError, match="Expected type annotation identifier or string"):
            typed_doc.select("node[()port=8080]")

    def test_invalid_token_in_type_annotation_raises_selector_error(
        self, typed_doc: KdlDocument
    ) -> None:
        with pytest.raises(SelectorError, match="Expected type annotation identifier or string"):
            typed_doc.select("(=)node")

        with pytest.raises(SelectorError, match="Expected type annotation identifier or string"):
            typed_doc.select("(>)node")

    def test_missing_rparen_raises_selector_error(self, typed_doc: KdlDocument) -> None:
        with pytest.raises(SelectorError, match="Expected RPAREN"):
            typed_doc.select('("my/type"node')


# ---------------------------------------------------------------------------
# Disambiguated property filter keys and positional argument differentiation (Ticket 04)
# ---------------------------------------------------------------------------

KDL_ATTR_KEYS_DOC = r"""/- kdl-version 2

service "my-app" "backend" "0"="prop_zero" "1"="prop_one" "app.name"="api-gateway" "foo:bar"="baz" "a>b"="gt_val" "c+d"="plus_val" "x~y"="tilde_val" "a,b"="comma_val" "nested[key]"="bracket_val" "spaced key"="space_val" "has'single"="single_quote_val" "has\"double"="double_quote_val" port=(u16)8080 {
    route "/users" "GET" "api.version"="v1" auth=#true "0"="route_zero"
    route "/items" "POST" "api.version"="v2" auth=#false "0"="item_zero"
    config "db.host"="localhost" "foo.bar"="cfg_val"
}

service "secondary" "frontend" "0"="sec_zero" "app.name"="web-client" "foo:bar"="qux" {
    route "/dashboard" "GET" "api.version"="v1" auth=#true
}

worker "worker-1" "active" 100 "0"="w0" "1"="w1" "2"="w2"
"""


@pytest.fixture()
def attr_doc() -> KdlDocument:
    return parse(KDL_ATTR_KEYS_DOC)


class TestDisambiguatedAttributeKeysQuotes:
    def test_double_quoted_property_keys(self, attr_doc: KdlDocument) -> None:
        r = attr_doc.select('service["app.name"="api-gateway"]')
        assert _first_args(r) == ["my-app"]
        r2 = attr_doc.select('service["app.name"="web-client"]')
        assert _first_args(r2) == ["secondary"]

    def test_single_quoted_property_keys(self, attr_doc: KdlDocument) -> None:
        r = attr_doc.select("service['app.name'='api-gateway']")
        assert _first_args(r) == ["my-app"]
        r2 = attr_doc.select("service['app.name'='web-client']")
        assert _first_args(r2) == ["secondary"]

    def test_single_quoted_key_with_double_quoted_value(self, attr_doc: KdlDocument) -> None:
        r = attr_doc.select('service[\'app.name\'="api-gateway"]')
        assert _first_args(r) == ["my-app"]

    def test_double_quoted_key_with_single_quoted_value(self, attr_doc: KdlDocument) -> None:
        r = attr_doc.select("service[\"app.name\"='api-gateway']")
        assert _first_args(r) == ["my-app"]

    def test_special_characters_in_quoted_keys(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select('service["foo:bar"="baz"]')) == ["my-app"]
        assert _first_args(attr_doc.select("service['foo:bar'='baz']")) == ["my-app"]
        assert _first_args(attr_doc.select('service["foo:bar"="qux"]')) == ["secondary"]

        assert _first_args(attr_doc.select('service["a>b"="gt_val"]')) == ["my-app"]
        assert _first_args(attr_doc.select("service['a>b'='gt_val']")) == ["my-app"]

        assert _first_args(attr_doc.select('service["c+d"="plus_val"]')) == ["my-app"]
        assert _first_args(attr_doc.select("service['c+d'='plus_val']")) == ["my-app"]

        assert _first_args(attr_doc.select('service["x~y"="tilde_val"]')) == ["my-app"]
        assert _first_args(attr_doc.select("service['x~y'='tilde_val']")) == ["my-app"]

        assert _first_args(attr_doc.select('service["a,b"="comma_val"]')) == ["my-app"]
        assert _first_args(attr_doc.select("service['a,b'='comma_val']")) == ["my-app"]

        assert _first_args(attr_doc.select('service["nested[key]"="bracket_val"]')) == ["my-app"]
        assert _first_args(attr_doc.select("service['nested[key]'='bracket_val']")) == ["my-app"]

        assert _first_args(attr_doc.select('service["spaced key"="space_val"]')) == ["my-app"]
        assert _first_args(attr_doc.select("service['spaced key'='space_val']")) == ["my-app"]

        assert _first_args(attr_doc.select('service["has\'single"="single_quote_val"]')) == ["my-app"]
        assert _first_args(attr_doc.select("service['has\"double'='double_quote_val']")) == ["my-app"]

    def test_quoted_key_operators(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select('service["app.name"^="api"]')) == ["my-app"]
        assert _first_args(attr_doc.select('service["app.name"$="client"]')) == ["secondary"]
        assert _first_args(attr_doc.select('service["app.name"~="gate"]')) == ["my-app"]

    def test_quoted_key_existence_filter(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select('service["app.name"]')) == ["my-app", "secondary"]
        assert _first_args(attr_doc.select("service['foo:bar']")) == ["my-app", "secondary"]
        assert _first_args(attr_doc.select('service["a>b"]')) == ["my-app"]
        assert _first_args(attr_doc.select('service["nonexistent"]')) == []

    def test_type_annotated_value_with_quoted_key(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select('service[(u16)"port"=8080]')) == ["my-app"]
        assert _first_args(attr_doc.select('service[(u32)"port"=8080]')) == []


class TestDisambiguatedAttributeKeysEscapes:
    def test_unquoted_key_with_escaped_dot(self, attr_doc: KdlDocument) -> None:
        r = attr_doc.select(r'service[app\.name="api-gateway"]')
        assert _first_args(r) == ["my-app"]
        r2 = attr_doc.select(r'service[app\.name="web-client"]')
        assert _first_args(r2) == ["secondary"]

    def test_unquoted_key_with_escaped_colon(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select(r'service[foo\:bar="baz"]')) == ["my-app"]
        assert _first_args(attr_doc.select(r'service[foo\:bar="qux"]')) == ["secondary"]

    def test_unquoted_key_with_escaped_combinators(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select(r'service[a\>b="gt_val"]')) == ["my-app"]
        assert _first_args(attr_doc.select(r'service[c\+d="plus_val"]')) == ["my-app"]
        assert _first_args(attr_doc.select(r'service[x\~y="tilde_val"]')) == ["my-app"]
        assert _first_args(attr_doc.select(r'service[a\,b="comma_val"]')) == ["my-app"]

    def test_unquoted_key_with_escaped_brackets(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select(r'service[nested\[key\]="bracket_val"]')) == ["my-app"]

    def test_unquoted_key_with_escaped_space(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select(r'service[spaced\ key="space_val"]')) == ["my-app"]

    def test_unquoted_key_with_escaped_number(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select(r'service[\0="prop_zero"]')) == ["my-app"]
        assert _first_args(attr_doc.select(r'service[\0="sec_zero"]')) == ["secondary"]

    def test_unquoted_key_escaped_operators(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select(r'service[app\.name^="api"]')) == ["my-app"]
        assert _first_args(attr_doc.select(r'service[foo\:bar$="az"]')) == ["my-app"]
        assert _first_args(attr_doc.select(r'service[a\>b~="gt"]')) == ["my-app"]

    def test_unquoted_key_escaped_existence(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select(r"service[app\.name]")) == ["my-app", "secondary"]
        assert _first_args(attr_doc.select(r"service[foo\:bar]")) == ["my-app", "secondary"]
        assert _first_args(attr_doc.select(r"service[a\>b]")) == ["my-app"]


class TestPositionalArgumentVsNumericPropertyKey:
    def test_unquoted_number_matches_positional_arg_0(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select('service[0="my-app"]')) == ["my-app"]
        assert _first_args(attr_doc.select('service[0="secondary"]')) == ["secondary"]
        assert _first_args(attr_doc.select('service[0="prop_zero"]')) == []

    def test_quoted_number_matches_property_with_string_key(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select('service["0"="prop_zero"]')) == ["my-app"]
        assert _first_args(attr_doc.select("service['0'='prop_zero']")) == ["my-app"]
        assert _first_args(attr_doc.select('service["0"="sec_zero"]')) == ["secondary"]
        assert _first_args(attr_doc.select('service["0"="my-app"]')) == []
        assert _first_args(attr_doc.select("service['0'='my-app']")) == []

    def test_unquoted_vs_quoted_number_at_index_1(self, attr_doc: KdlDocument) -> None:
        assert _first_args(attr_doc.select('service[1="backend"]')) == ["my-app"]
        assert _first_args(attr_doc.select('service[1="frontend"]')) == ["secondary"]
        assert _first_args(attr_doc.select('service["1"="prop_one"]')) == ["my-app"]
        assert _first_args(attr_doc.select("service['1'='prop_one']")) == ["my-app"]
        assert _first_args(attr_doc.select('service[1="prop_one"]')) == []
        assert _first_args(attr_doc.select('service["1"="backend"]')) == []

    def test_existence_unquoted_vs_quoted_number(self, attr_doc: KdlDocument) -> None:
        # worker has args: "worker-1" (0), "active" (1), 100 (2)
        # worker has props: "0"="w0", "1"="w1", "2"="w2"
        assert len(attr_doc.select("worker[0]")) == 1
        assert len(attr_doc.select("worker[1]")) == 1
        assert len(attr_doc.select("worker[2]")) == 1
        assert len(attr_doc.select("worker[3]")) == 0

        assert len(attr_doc.select('worker["0"]')) == 1
        assert len(attr_doc.select("worker['0']")) == 1
        assert len(attr_doc.select('worker["1"]')) == 1
        assert len(attr_doc.select('worker["2"]')) == 1
        assert len(attr_doc.select('worker["3"]')) == 0

    def test_operators_on_numeric_keys(self, attr_doc: KdlDocument) -> None:
        assert len(attr_doc.select('worker["0"^="w"]')) == 1
        assert len(attr_doc.select('worker["0"$="0"]')) == 1
        assert len(attr_doc.select('worker["0"~="w"]')) == 1
        assert len(attr_doc.select('worker[1^="act"]')) == 1
        assert len(attr_doc.select('worker[1$="ive"]')) == 1
        assert len(attr_doc.select('worker[1~="cti"]')) == 1


class TestDisambiguatedAttributeKeysCombinatorsAndPseudoClasses:
    def test_child_combinator_with_disambiguated_keys(self, attr_doc: KdlDocument) -> None:
        r = attr_doc.select('service["app.name"="api-gateway"] > route["api.version"="v1"]')
        assert len(r) == 1
        assert r[0].get_arg(0) == "/users"

        r2 = attr_doc.select('service[0="my-app"] > route["0"="route_zero"]')
        assert len(r2) == 1
        assert r2[0].get_arg(0) == "/users"

        r3 = attr_doc.select('service[0="my-app"] > route["0"="item_zero"]')
        assert len(r3) == 1
        assert r3[0].get_arg(0) == "/items"

    def test_descendant_combinator_with_disambiguated_keys(self, attr_doc: KdlDocument) -> None:
        r = attr_doc.select('service[\'foo:bar\'="baz"] config["db.host"="localhost"]')
        assert len(r) == 1
        assert r[0].name == "config"

    def test_multiple_filters_on_same_node(self, attr_doc: KdlDocument) -> None:
        r = attr_doc.select('service[0="my-app"][1="backend"]["0"="prop_zero"]["app.name"="api-gateway"]')
        assert _first_args(r) == ["my-app"]

        r_mismatch = attr_doc.select('service[0="my-app"][1="frontend"]')
        assert r_mismatch == []

    def test_pseudo_class_not_with_disambiguated_keys(self, attr_doc: KdlDocument) -> None:
        r = attr_doc.select('service:not(["app.name"="web-client"])')
        assert _first_args(r) == ["my-app"]

        r2 = attr_doc.select('service:not([0="secondary"])')
        assert _first_args(r2) == ["my-app"]

        r3 = attr_doc.select('service:not(["0"="sec_zero"])')
        assert _first_args(r3) == ["my-app"]

        r4 = attr_doc.select(r'service:not([foo\:bar="qux"])')
        assert _first_args(r4) == ["my-app"]

    def test_pseudo_class_has_with_disambiguated_keys(self, attr_doc: KdlDocument) -> None:
        r = attr_doc.select('service:has(> route["api.version"="v2"])')
        assert _first_args(r) == ["my-app"]

        r2 = attr_doc.select('service:has(> route["0"="item_zero"])')
        assert _first_args(r2) == ["my-app"]

        r3 = attr_doc.select('service:has(config["db.host"="localhost"])')
        assert _first_args(r3) == ["my-app"]


class TestDisambiguatedAttributeKeysPublicAPIs:
    def test_select_returns_list(self, attr_doc: KdlDocument) -> None:
        r = attr_doc.select('service["0"="prop_zero"]')
        assert isinstance(r, list)
        assert len(r) == 1
        assert r[0].get_arg(0) == "my-app"

    def test_select_one_returns_node_or_none(self, attr_doc: KdlDocument) -> None:
        node = attr_doc.select_one('service["app.name"="api-gateway"]')
        assert node is not None
        assert node.get_arg(0) == "my-app"

        none_node = attr_doc.select_one('service["app.name"="nonexistent"]')
        assert none_node is None

    def test_kdl_node_select_and_select_one(self, attr_doc: KdlDocument) -> None:
        srv = attr_doc.select_one('service["0"="prop_zero"]')
        assert srv is not None

        routes = srv.select('route["api.version"="v1"]')
        assert len(routes) == 1
        assert routes[0].get_arg(0) == "/users"

        route = srv.select_one('route["api.version"="v1"]')
        assert route is not None
        assert route.get_arg(0) == "/users"

        missing = srv.select_one('route["api.version"="v99"]')
        assert missing is None

    def test_kdl_node_matches(self, attr_doc: KdlDocument) -> None:
        srv = attr_doc.select_one('service[0="my-app"]')
        assert srv is not None

        # Positional arg index
        assert srv.matches('service[0="my-app"]') is True
        assert srv.matches('service[0="prop_zero"]') is False

        # Quoted property keys
        assert srv.matches('service["0"="prop_zero"]') is True
        assert srv.matches("service['0'='prop_zero']") is True
        assert srv.matches('service["0"="my-app"]') is False
        assert srv.matches("service['0'='my-app']") is False

        assert srv.matches('service["app.name"="api-gateway"]') is True
        assert srv.matches("service['app.name'='api-gateway']") is True
        assert srv.matches('service["app.name"="web-client"]') is False

        # Backslash escaped property keys
        assert srv.matches(r'service[app\.name="api-gateway"]') is True
        assert srv.matches(r'service[foo\:bar="baz"]') is True
        assert srv.matches(r'service[foo\:bar="qux"]') is False
        assert srv.matches(r'service[\0="prop_zero"]') is True


class TestDisambiguatedAttributeKeysErrors:
    def test_unterminated_double_quote_key(self, attr_doc: KdlDocument) -> None:
        with pytest.raises(SelectorError, match="Unterminated string"):
            attr_doc.select('service["unterminated]')

    def test_unterminated_single_quote_key(self, attr_doc: KdlDocument) -> None:
        with pytest.raises(SelectorError, match="Unterminated string"):
            attr_doc.select("service['unterminated]")

    def test_unterminated_escape_in_key(self, attr_doc: KdlDocument) -> None:
        with pytest.raises(SelectorError, match="Unterminated escape sequence"):
            attr_doc.select("service[app\\")

    def test_float_positional_index(self, attr_doc: KdlDocument) -> None:
        with pytest.raises(SelectorError, match="Expected integer index"):
            attr_doc.select('service[1.5="val"]')

    def test_invalid_token_as_key(self, attr_doc: KdlDocument) -> None:
        with pytest.raises(SelectorError, match="Expected key name or index"):
            attr_doc.select('service[#true="val"]')


class TestDisambiguatedAttributeKeysBackwardCompatibility:
    def test_standard_unquoted_properties(self, doc: KdlDocument) -> None:
        assert _names(doc.select("app[version]")) == ["app"]
        assert _names(doc.select('app[version="1.0.0"]')) == ["app"]
        assert _first_args(doc.select("server[port=8080]")) == ["primary"]
        assert _first_args(doc.select("server[tls=#true]")) == ["primary"]

    def test_standard_positional_arguments(self, doc: KdlDocument) -> None:
        assert _first_args(doc.select("server[0]")) == ["primary", "replica"]
        assert _first_args(doc.select('server[0="primary"]')) == ["primary"]
        assert _first_args(doc.select('route[1="/api/users"]')) == ["GET", "POST"]
        assert _first_args(doc.select('route[*="POST"]')) == ["POST"]

    def test_standard_property_type_annotations(self, doc: KdlDocument) -> None:
        assert _names(doc.select("backend[(u16)port=6379]")) == ["backend"]
        assert _names(doc.select("limits[(u32)max-conn=1000]")) == ["limits"]


