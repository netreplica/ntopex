#!/usr/bin/env python3

import os
import sys
import json
import toml
import pynetbox
import networkx as nx
import matplotlib.pyplot as plt



class NB_Network:
    def __init__(self):
        self.config = {}
        self.nodes = []
        self.devices = []
        self.cable_ids = []
        self.interfaces = []
        self.device_ids = []
        self.interface_ids = []


class NB_Factory:
    def __init__(self, config):
        self.config = config
        self.nb_net = NB_Network()
        self.G = nx.Graph()
        self.N = nx.Graph()  # graph with names as IDs for quick visual validation only
        self.graph_plot = None
        self.nb_session = pynetbox.api(self.config['nb_api_url'], token=self.config['nb_api_token'], threading=True)
        self.nb_site = self.nb_session.dcim.sites.get(name=config['export_site'])
        self._get_nb_device_info()
        self._build_network_graph()


    def _get_nb_device_info(self):
        for device in list(self.nb_session.dcim.devices.filter(site_id=self.nb_site.id, role=self.config['export_device_roles'])):
            d = {
                "id": device.id,
                "type": "device",
                "name": device.name,
                "node_id": -1,
            }
            self.nb_net.nodes.append(d)
            d["node_id"] = len(self.nb_net.nodes) - 1
            self.nb_net.devices.append(d)
            self.nb_net.device_ids.append(
                device.id)  # index of the device in the devices list will match its ID index in device_ids list

            for interface in list(self.nb_session.dcim.interfaces.filter(device_id=device.id)):
                if "base" in interface.type.value and interface.cable:  # only connected ethernet interfaces
                    print(device.name, ":", interface, ":", interface.type.value)
                    i = {
                        "id": interface.id,
                        "type": "interface",
                        "name": interface.name,
                        "node_id": -1,
                    }
                    self.nb_net.nodes.append(i)
                    i["node_id"] = len(self.nb_net.nodes) - 1
                    self.nb_net.interfaces.append(i)
                    self.nb_net.interface_ids.append(
                        interface.id)  # index of the interface in the interfaces list will match its ID index in interface_ids list
                    self.nb_net.cable_ids.append(interface.cable.id)

    def _build_network_graph(self):
        for cable in list(self.nb_session.dcim.cables.filter(id=self.nb_net.cable_ids)):
            if len(cable.a_terminations) == 1 and len(cable.b_terminations) == 1:
                int_a = cable.a_terminations[0]
                int_b = cable.b_terminations[0]
                if isinstance(int_a, pynetbox.models.dcim.Interfaces) and isinstance(int_b,
                                                                                     pynetbox.models.dcim.Interfaces):
                    print("{}:{} <> {}:{}".format(int_a.device, int_a, int_b.device, int_b))
                    d_a = self.nb_net.devices[self.nb_net.device_ids.index(int_a.device.id)]
                    d_b = self.nb_net.devices[self.nb_net.device_ids.index(int_b.device.id)]
                    self.G.add_nodes_from([
                        (d_a["node_id"], {"side": "a", "type": "device", "device": d_a}),
                        (d_b["node_id"], {"side": "b", "type": "device", "device": d_b}),
                    ])
                    self.N.add_nodes_from([
                        (d_a["name"], {"side": "a", "type": "device", "device": d_a}),
                        (d_b["name"], {"side": "b", "type": "device", "device": d_b}),
                    ])
                    i_a = self.nb_net.interfaces[self.nb_net.interface_ids.index(int_a.id)]
                    i_b = self.nb_net.interfaces[self.nb_net.interface_ids.index(int_b.id)]
                    self.G.add_nodes_from([
                        (i_a["node_id"], {"side": "a", "type": "interface", "interface": i_a}),
                        (i_b["node_id"], {"side": "b", "type": "interface", "interface": i_b}),
                    ])
                    self.N.add_nodes_from([
                        (i_a["name"], {"side": "a", "type": "interface", "interface": i_a}),
                        (i_b["name"], {"side": "b", "type": "interface", "interface": i_b}),
                    ])
                    self.G.add_edges_from([
                        (d_a["node_id"], i_a["node_id"]),
                        (d_b["node_id"], i_b["node_id"]),
                    ])
                    self.N.add_edges_from([
                        (d_a["name"], i_a["name"]),
                        (d_b["name"], i_b["name"]),
                    ])
                    self.G.add_edges_from([
                        (i_a["node_id"], i_b["node_id"]),
                    ])
                    self.N.add_edges_from([
                        (i_a["name"], i_b["name"]),
                    ])
        self._build_network_graph_image()

    def _build_network_graph_image(self):
        self.graph_plot = plt.subplot(121)
        nx.draw(self.G, with_labels=True, font_weight='bold')
        self.graph_plot = plt.subplot(122)
        nx.draw(self.N, with_labels=True, font_size='6')

    def export_graph_image(self):
        filename = f'{self.config["export_site"]}.graph.png'
        plt.savefig(filename)
        print(f'Graph image saved to {filename}')

    def export_graph_gml(self):
        #print("\n".join(nx.generate_gml(G)))
        nx.write_gml(self.G, self.config['export_site'] + ".gml")
        print(f'Graph GML saved to {self.config["export_site"]}.gml')

    def export_graph_json(self):
        cyjs = nx.cytoscape_data(self.G)
        #print(json.dumps(cyjs, indent=4))
        with open(self.config['export_site'] + ".cyjs", 'w', encoding='utf-8') as f:
            json.dump(cyjs, f, indent=4)
        print(f'Graph JSON saved to {self.config["export_site"]}.cyjs')


def load_config(filename):
    config = {}
    with open(filename, 'r') as f:
        nb_config = toml.load(f)
    config['export_site'] = os.getenv('EXPORT_SITE', nb_config['export_site'])
    config['nb_api_url'] = os.getenv('NB_API_URL', nb_config['nb_api_url'])
    config['nb_api_token'] = os.getenv('NB_API_TOKEN', nb_config['nb_api_token'])
    config['export_device_roles'] = os.getenv('EXPORT_DEVICE_ROLES', nb_config['export_device_roles'])
    return config




def main():

    config = load_config('config.toml')
    nb_network = NB_Factory(config)
    nb_network.export_graph_image()
    nb_network.export_graph_gml()
    nb_network.export_graph_json()

    return 0


if __name__ == '__main__':
    sys.exit(main())