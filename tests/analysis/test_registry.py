from music_recommendations.analysis import registry


def test_verified_node_names_from_spec():
    g = registry.HEADS["genre"]
    assert g.input_node == "serving_default_model_Placeholder"
    assert g.output_node == "PartitionedCall:0"
    assert g.n_out == 400
    m = registry.HEADS["moodtheme"]
    assert m.input_node == "model/Placeholder"
    assert m.output_node == "model/Sigmoid"
    assert m.n_out == 56


def test_urls_are_wellformed():
    for head in registry.HEADS.values():
        assert registry.model_url(head.filename).startswith(
            "https://essentia.upf.edu/models/classification-heads/"
        )
