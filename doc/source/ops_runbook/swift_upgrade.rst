=====================
Swift Rolling Upgrade
=====================

Overview of upgrade process
~~~~~~~~~~~~~~~~~~~~~~~~~~~
#.	Upgrade a single storage (ACO) node ('canary' node)
#.	Observe upgraded storage node for problems or anomalies
#.	Upgrade all other storage nodes (1 at a time)
#.	Upgrade a single proxy node ('canary' node)
#.	Observe upgraded proxy node for problems or anomalies
#.	Upgrade all other proxy nodes (1 at a time)

Upgrading a Storage Node
------------------------

.. NOTE: tested on a multi-node (VMs) Swift cluster (2 Proxy, 3 ACO)

1.	Stop all background Swift jobs

.. code::

   $ swift-init rest stop

2.	Shutdown all Swift storage processes

.. code::

   $ swift-init {account|container|object} shutdown --graceful

3.	Upgrade to a newer version of Swift

(a) Upgrade your local Swift repository from source code

.. code::

   $ git tag –l  # lists all the tags for the given repo
   $ git checkout <tag_to_update_to>

(b) Upgrade packages

.. code::

   $ sudo pip install –r requirements.txt --upgrade
   $ sudo pip install –r test-requirements.txt –upgrade
   $ sudo python setup.py install

4.	Reboot server to run any availible kernel upgrades

.. code::

   $ sudo reboot

5.	Start all storage services

.. code::

   $ swift-init {account|container|object} start

6.	Start background Swift jobs

.. code::

   $ swift-init rest start


Upgrading a Proxy Node
----------------------

1.	Shutdown the Swift proxy server

.. code::

   $ swift-init proxy shutdown [ --graceful ]

2. Create a ``disable_path`` file system path in the proxy
   config to cause the ``/heatlthcheck`` endpoint to return
   a ``503 service unavailable`` error.
   (See [3] for more information)

3.	Upgrade to a newer version of Swift

(a) Upgrade local Swift repository from source code

.. code::

   $ git tag –l # lists all the tags for the given repo
   $ git checkout <tag_to_update_to>

(b) Upgrade packages

.. code::

   $ sudo pip install –r requirements.txt --upgrade
   $ sudo pip install –r test-requirements.txt –upgrade
   $ sudo python setup.py install

4. Update the proxy configs with any changes

5.	Reboot server to run any availible kernel upgrades

.. code::

   $ sudo reboot

6.	Start the proxy service

.. code::

   $ swift-init proxy start

7. Remove the ``disable_path`` file to re-enable health check


Terminology
~~~~~~~~~~~

Control Plane
-------------
The control plane manages data that is stored across storage devices.
In Swift, the proxy service can be considered the control plane. The proxy
service provides access to the underlying stored data and storage services,
and also requests for both user account logins and CRUD (Create, Read,
Update, and Delete) resources, such as Swift objects. If a control plane such
as the proxy sercice were to crash, only access to data would be lost, not the
data itself.

Data Plane
----------
The data plane manages data, storage devices, and the read/write operations to
the data stored on devices. The data plane manages updating the databases, file
access Input/Output or filesystem tasks. In Swift, storage services (account,
container, object) can be considered the data plane. The data plane
notifies the control plane of possible ``running out of disk space`` or drive
failure scenarios. If a data plane node were to crash, data in that node may be
lost.

Zero Downtime Rolling Upgrade
-----------------------------
Swift services, by design, provide high availability and redundancy. This
feature allows for zero-downtime rolling upgrades. For example, during the
upgrade of a single storage node, CRUD requests (made to the proxy server) will
continue without any interruption of service. This zero-downtime upgrade is
possible because other storage nodes are still online and accessible
by the proxy server. The newly upgraded storage node will gain data consistency
with the remaining storage nodes during the next replication cycle that
occurs after being brought online.

Similarly, there would be no downtime during upgrade of a single proxy
node as the load balancer will direct requests to other proxy nodes
within the cluster. The end user will not experience any service
interruptions during this upgrade process.

The key to high availability (zero downtime) during Swift upgrades is:
(1) having multiple storage nodes and multiple proxy nodes, and
(2) performing upgrades one node at a time.

References
~~~~~~~~~~
[1] https://www.swiftstack.com/blog/2013/12/20/upgrade-openstack-swift-no-downtime/

[2] https://www.blueboxcloud.com/resources/user-resources/upgrading-openstack-a-best-practices-guide

[3] https://github.com/openstack/swift/blob/master/etc/proxy-server.conf-sample#L408
