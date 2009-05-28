#!/usr/bin/env python
# Copyright 2009 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
requires pydot

usage: graph_data.py [fixture1.json, fixture2.json, ...]

writes a png to out.png

"""
import pydot
import pprint
import simplejson
#import igraph

def graph_from_models_dot(*models):
  graph = pydot.Dot(graph_type='digraph')
  
  streams = {}
  entries = {}

  actor_graph = pydot.Cluster(graph_name='actors', suppress_disconnected=False)
  #graph.add_subgraph(actor_graph)
  for dataset in models:
    for d in dataset:
      if d['model'].lower() == 'common.relation':
        continue
        # process this as an edge
        actor_graph.add_edge(pydot.Edge(src=d['fields']['owner'], 
                                  dst=d['fields']['target'], 
                                  label=d['fields']['relation']))

      elif d['model'].lower() == 'common.actor':
        # process this as a node
        if d['fields']['privacy'] == 3:
          color = 'green'
        else:
          color = 'red'
        graph.add_node(pydot.Node(name=d['fields']['nick'],
                                  color=color))
      elif d['model'].lower() == 'common.stream':
        subgraph_name = d['pk'].replace("/", "_").replace("@", "_").replace(".", "_").replace("#", "X")
        streams[d['pk']] = pydot.Cluster(graph_name=subgraph_name, suppress_disconnected=False)
        streams[d['pk']].add_node(pydot.Node(name=d['pk']))
        graph.add_edge(pydot.Edge(src=d['fields']['owner'], 
                                  dst=d['pk'], 
                                  label=d['fields']['type']))

        graph.add_subgraph(streams[d['pk']])

      elif d['model'].lower() == 'common.streamentry':
        streams[d['fields']['stream']].add_edge(pydot.Edge(src=d['fields']['stream'],
                                                           dst=d['pk'],
                                                           label='entry'))
        pass
      elif d['model'].lower() == 'common.inboxentry':
        continue
        entry_name = d['pk'].replace("/", "_").replace("@", "_").replace(".", "_").replace("#", "X")
        entries[d['pk']] = pydot.Cluster(graph_name=entry_name, suppress_disconnected=False)
        graph.add_subgraph(entries[d['pk']])

        for inbox in d['fields']['inbox']:
          entries[d['pk']].add_edge(pydot.Edge(src=d['pk'][len('inboxentry/'):],
                                               dst=inbox,
                                                ))
                                                           
  return graph
  

#def graph_from_models_igraph(*models):
#  edge_attrs = {"name": []}
#  edges = []
#  vertex_attrs = {"name": []}
#  i = 0
#  for dataset in models:
#    for d in dataset:
#      if d['model'].lower() == 'common.relation':
#        continue
#      j = i
#      vertex_attrs['name'].append(d['pk'])
#      for k, v in d['fields'].iteritems():
#        if not isinstance(v, basestring):
#          continue
#        if k in ('created_at', 
#        i += 1
        
#        vertex_attrs['name'].append(v)
#        edges.append((j, i))
#        edge_attrs['name'].append(k)
        
#  #graph = igraph.Graph(directed=True, edges=edges, 
#  #                     edge_attrs=edge_attrs, vertex_attrs=vertex_attrs)
#  graph = igraph.Graph(directed=True)
#  graph.add_vertices(len(vertex_attrs['name']))
#  for iv in range(len(vertex_attrs['name'])):
#    graph.vs[iv]['label'] = vertex_attrs['name'][iv]

#  for e in edges:
#    graph.add_edges(e)

#  for iv in range(len(edge_attrs['name'])):
#    graph.es[iv]['label'] = edge_attrs['name'][iv]
    
#  return graph


if __name__ == "__main__":
  import sys
  models = sys.argv[1:]
  models_ref = []
  for m in models:
    data_file = open(m)
    models_ref.append(simplejson.load(data_file))
    data_file.close()
  

  graph = graph_from_models_dot(*models_ref)
  print graph.to_string()
  graph.write_png(path='out.png')
  #graph = graph_from_models_igraph(*models_ref)
  #graph.write_graphml('out.graphml')
