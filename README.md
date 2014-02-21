ishuttle
========

The purpose of ishuttle (interactive shuttle) is to make more convenient the process of copying in-progress code to all of your remote IPython engines during code testing. You just give the main class, Shuttle, a copy of your IPython Client and a remote working directory to use, and it will scp over the modules you want to remotely import/reload before importing/reloading.


#### Disclaimer:

Use this code at your own risk. I take no responsibility if it doesn't work and/or screws up your stuff.

#### Prerequisites:

* Working ipython parallel profile with remote engines
* Passwordless ssh setup between you and all engine computers

#### Example:
-------------

```python
import IPython.parallel
import ishuttle
import my_module as mm

# Create a client for the cluster with remote engines
rc = IPython.parallel.Client(profile='remote_ssh_engines')
dview = rc[:]

# Create a shuttle object; the engines' working directory
# is switched to '/Remote/engine/server/scratch' after its creation
s = ishuttle.Shuttle(rc, '/Remote/engine/server/scratch')

# Make my_module available on all engines as mm. This code scp's the
# module over, imports it as mm, then reloads it.
s.remote_import('my_module', import_as='mm')

# Apply our favourite function from our favourite module
dview.apply_sync(mm.my_func, 'favourite argument for my_func')
```
