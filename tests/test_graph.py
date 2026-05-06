from agent.graph import build_graph

def test_graph_compiles():
    assert build_graph() is not None

def test_graph_has_expected_nodes():
    g = build_graph()
    expected = {"ingest","extract","check_renewals","benchmark","draft_memos","alert"}
    assert expected.issubset(set(g.nodes.keys()))
