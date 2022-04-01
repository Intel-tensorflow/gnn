"""Tests for padding_ops Keras layers."""

import enum
import os

from absl.testing import parameterized
import tensorflow as tf
from tensorflow_gnn.graph import adjacency as adj
from tensorflow_gnn.graph import graph_tensor as gt
from tensorflow_gnn.graph import preprocessing_common
from tensorflow_gnn.graph.keras import keras_tensors  # For registration. pylint: disable=unused-import
from tensorflow_gnn.graph.keras.layers import padding_ops


class ReloadModel(int, enum.Enum):
  """Controls how to reload a model for further testing after saving."""
  SKIP = 0
  SAVED_MODEL = 1
  KERAS = 2


class PadToTotalSizesTest(tf.test.TestCase, parameterized.TestCase):

  def _make_test_graph(self):
    return gt.GraphTensor.from_pieces(
        context=gt.Context.from_fields(
            features={"label": tf.constant([42])}),
        node_sets={"nodes": gt.NodeSet.from_fields(
            sizes=tf.constant([1]),
            features={"feature": tf.constant([[1., 2.]])})},
        edge_sets={"edges": gt.EdgeSet.from_fields(
            sizes=tf.constant([1]),
            adjacency=adj.Adjacency.from_indices(("nodes", tf.constant([0])),
                                                 ("nodes", tf.constant([0]))),
            features={"weight": tf.constant([1.0])})})

  @parameterized.named_parameters(
      ("", ReloadModel.SKIP),
      ("Restored", ReloadModel.SAVED_MODEL),
      ("RestoredKeras", ReloadModel.KERAS))
  def test(self, reload_model):
    input_graph = self._make_test_graph()
    sc = preprocessing_common.SizeConstraints(
        total_num_components=2,
        total_num_nodes={"nodes": 3},
        total_num_edges={"edges": tf.constant(4)})  # Test conversion to int.
    pad = padding_ops.PadToTotalSizes(sc)

    inputs = tf.keras.layers.Input(type_spec=input_graph.spec)
    outputs = pad(inputs)
    model = tf.keras.Model(inputs, outputs)
    if reload_model:
      export_dir = os.path.join(self.get_temp_dir(), "padding-model")
      model.save(export_dir, include_optimizer=False)
      if reload_model == ReloadModel.KERAS:
        model = tf.keras.models.load_model(export_dir)
      else:
        model = tf.saved_model.load(export_dir)

    graph, mask = model(input_graph)
    self.assertAllEqual([True, False], mask)
    self.assertAllEqual(2, graph.num_components)
    self.assertAllEqual([42, 0], graph.context["label"])
    nodes = graph.node_sets["nodes"]
    self.assertAllEqual([1, 2], nodes.sizes)
    self.assertAllEqual([[1., 2.], [0., 0.], [0., 0.]], nodes["feature"])
    edges = graph.edge_sets["edges"]
    self.assertAllEqual([1, 3], edges.sizes)
    self.assertAllEqual([1., 0., 0., 0.], edges["weight"])


if __name__ == "__main__":
  tf.test.main()
