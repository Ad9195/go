// Copyright 2016 Platina Systems, Inc. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package unix

import (
	"github.com/platinasystems/go/elib"
	"github.com/platinasystems/go/elib/cli"
	"github.com/platinasystems/go/elib/iomux"
	"github.com/platinasystems/go/internal/netlink"
	"github.com/platinasystems/go/vnet"

	"fmt"
	"io/ioutil"
	"os"
	"path"
	"sort"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

type inotify_event struct {
	watch_descriptor int32
	mask             uint32
	cookie           uint32
	len              uint32
}

func decode(b []byte, i int) (e *inotify_event, name string, i_next int) {
	e = (*inotify_event)(unsafe.Pointer(&b[i]))
	j := i + 16
	len := strings.IndexByte(string(b[j:]), 0)
	name = string(b[j : j+len])
	i_next = j + int(e.len)
	return
}

func (m *net_namespace_main) read_dir(dir_name string, f func(dir, name string, is_del bool)) (err error) {
	// Collect existing files in directory.
	var fis []os.FileInfo
	if fis, err = ioutil.ReadDir(dir_name); err != nil {
		return
	}
	for _, fi := range fis {
		f(dir_name, fi.Name(), false)
	}
	return
}

const (
	netnsDir               = "/var/run/netns"
	default_namespace_name = "default"
)

func (m *netlink_main) namespace_init() (err error) {
	nm := &m.net_namespace_main
	nm.m = m.m

	nm.rx_node.init(m.m.Vnet)
	nm.tx_node.init(nm)

	// Handcraft default name space.
	{
		ns := &nm.default_namespace
		ns.m = nm
		ns.name = default_namespace_name
		ns.nsid = -1
		ns.is_default = true
		if ns.ns_fd, err = nm.fd_for_path("", "/proc/self/ns/net"); err != nil {
			return
		}
		if ns.tx_raw_socket_fd, err = syscall.Socket(syscall.AF_PACKET, syscall.SOCK_RAW, 0); err != nil {
			return
		}
		ns.iomux_add()

		ns.index = nm.namespace_pool.GetIndex()
		nm.namespace_pool.entries[ns.index] = ns

		m.namespace_by_name = make(map[string]*net_namespace)
		m.namespace_by_name[ns.name] = ns

		if err = ns.configure(-1, -1); err != nil {
			return
		}
		ns.listen(m)
		ns.net_namespace_tx_node.init(nm)
	}

	// Setup initial namespaces.
	m.read_dir(netnsDir, m.watch_namespace_add_del)
	m.n_initial_namespace = uint(len(nm.namespace_by_name))
	return
}

// Called when initial netlink dump via netlink.Listen is done.
func (ns *net_namespace) netlink_dump_done(m *Main) (err error) {
	nm := &m.net_namespace_main
	nm.n_initial_namespace_done++
	if nm.n_initial_namespace_done == nm.n_initial_namespace {
		nm.n_initial_namespace_done = ^uint(0) // only happens once
		err = m.netlink_dump_done_for_all_namespaces()
	}
	return
}

func (m *netlink_main) watch_for_new_net_namespaces() {
	go m.watch_dir(netnsDir, m.watch_namespace_add_del)
}

func (m *net_namespace_main) watch_dir(dir_name string, f func(dir, name string, is_del bool)) (err error) {
	var fd, n int

	// Watch for new files added and existing files deleted.
	fd, err = syscall.InotifyInit()
	if err != nil {
		err = os.NewSyscallError("inotify init", err)
		return
	}

	if _, err = syscall.InotifyAddWatch(fd, dir_name, syscall.IN_CREATE|syscall.IN_DELETE); err != nil {
		err = os.NewSyscallError("inotify add watch", err)
		return
	}

	for {
		var buf [4096]byte
		if n, err = syscall.Read(fd, buf[:]); err != nil {
			panic(err)
		}
		for i := 0; i < n; {
			e, name, i_next := decode(buf[:], i)
			switch {
			case e.mask&syscall.IN_CREATE != 0:
				f(dir_name, name, false)
			case e.mask&syscall.IN_DELETE != 0:
				f(dir_name, name, true)
			}
			i = i_next
		}
	}
}

type net_namespace_interface struct {
	name      string
	namespace *net_namespace
	ifindex   uint32
	tuntap    *tuntap_interface
}

type net_namespace struct {
	m *net_namespace_main

	// Unique index allocated from index_pool.
	index uint

	name string

	// File descriptor for /proc/self/ns/net for default name space or /var/run/netns/NAME.
	ns_fd int

	nsid int

	tuntap_interface_by_ifindex map[uint32]*tuntap_interface
	dummy_interface_by_ifindex  map[uint32]*dummy_interface
	si_by_ifindex               map[uint32]vnet.Si

	is_default bool

	netlink_socket_fds [2]int
	netlink_socket_pair

	current_event *netlinkEvent

	interface_by_index map[uint32]*net_namespace_interface
	interface_by_name  map[string]*net_namespace_interface

	net_namespace_tx_node
}

//go:generate gentemplate -d Package=unix -id net_namespace -d PoolType=net_namespace_pool -d Type=*net_namespace -d Data=entries github.com/platinasystems/go/elib/pool.tmpl

type net_namespace_main struct {
	m                        *Main
	default_namespace        net_namespace
	namespace_by_name        map[string]*net_namespace
	tuntap_interface_by_name map[string]*tuntap_interface
	n_initial_namespace_done uint
	n_initial_namespace      uint
	interface_by_si          map[vnet.Si]*net_namespace_interface
	namespace_pool           net_namespace_pool
	rx_node                  rx_node
	tx_node                  tx_node
}

func (m *net_namespace_main) fd_for_path(dir, name string) (fd int, err error) {
	fd, err = syscall.Open(path.Join(dir, name), syscall.O_RDONLY, 0)
	return
}

func (m *netlink_main) nsid_for_path(dir, name string) (nsid int, err error) {
	var fd int
	if fd, err = m.fd_for_path(dir, name); err != nil {
		return
	}
	defer syscall.Close(fd)

	req := netlink.NewNetnsMessage()
	req.Type = netlink.RTM_GETNSID
	req.Flags = netlink.NLM_F_REQUEST
	req.AddressFamily = netlink.AF_UNSPEC
	req.Attrs[netlink.NETNSA_FD] = netlink.Uint32Attr(fd)
	rep := m.default_namespace.NetlinkTx(req, true)
	nsid = netlink.DefaultNsid
	switch v := rep.(type) {
	case *netlink.NetnsMessage:
		nsid = int(v.Attrs[netlink.NETNSA_NSID].(netlink.Int32Attr).Int())
	}
	return
}

func (e *netlinkEvent) netnsMessage(msg *netlink.NetnsMessage) (err error) {
	// Re-read directory to refresh name to nsid mapping.
	e.m.read_dir(netnsDir, e.m.watch_namespace_add_del)
	return
}

func (m *netlink_main) add_del_nsid(name string, nsid int, is_del bool) {
	if is_del {
		delete(m.namespace_by_name, name)
	} else {
		ns := &net_namespace{name: name, nsid: nsid}
		m.namespace_by_name[name] = ns
		ns.add(m)
	}
}

func (m *netlink_main) watch_namespace_add_del(dir, name string, is_del bool) {
	var (
		nsid int
		err  error
	)
	if !is_del {
		if nsid, err = m.nsid_for_path(dir, name); err != nil {
			panic(err)
		}
	} else {
		var ok bool
		if _, ok = m.namespace_by_name[name]; !ok {
			panic("delete unknown namespace " + name)
		}
	}
	m.add_del_nsid(name, nsid, is_del)
}

func (ns *net_namespace) add_del_interface(m *Main, msg *netlink.IfInfoMessage) {
	is_del := false
	switch msg.Header.Type {
	case netlink.RTM_NEWLINK:
	case netlink.RTM_DELLINK:
		is_del = true
	default:
		return
	}
	name := msg.Attrs[netlink.IFLA_IFNAME].String()
	index := msg.Index
	if !is_del {
		if ns.interface_by_index == nil {
			ns.interface_by_index = make(map[uint32]*net_namespace_interface)
			ns.interface_by_name = make(map[string]*net_namespace_interface)
		}
		intf, ok := ns.interface_by_index[index]
		name_changed := false
		if !ok {
			intf = &net_namespace_interface{
				namespace: ns,
				name:      name,
				ifindex:   index,
			}
			ns.interface_by_index[index] = intf
			ns.interface_by_name[name] = intf
		} else {
			name_changed = intf.name != name
		}
		if name_changed {
			delete(ns.interface_by_name, name)
			ns.interface_by_name[name] = intf
			intf.name = name

			// Change name of corresponding vnet interface.
			if tif, ok := ns.tuntap_interface_by_ifindex[index]; ok {
				tif.set_name(name)
			}
		} else {
			if tif, ok := m.tuntap_interface_by_name[name]; ok {
				if ns.si_by_ifindex == nil {
					ns.si_by_ifindex = make(map[uint32]vnet.Si)
				}
				ns.si_by_ifindex[index] = tif.si
				if m.interface_by_si == nil {
					m.interface_by_si = make(map[vnet.Si]*net_namespace_interface)
				}
				m.interface_by_si[tif.si] = intf
				// Interface moved to a new namespace?
				if tif.namespace != ns {
					tif.add_del_namespace(m, ns, is_del)
					tif.namespace = ns
				}
			}
		}
	} else {
		intf := ns.interface_by_index[index]
		if tif := intf.tuntap; tif != nil {
			tif.add_del_namespace(m, ns, is_del)
			tif.namespace = nil
			delete(ns.si_by_ifindex, index)
			delete(m.interface_by_si, tif.si)
		}
		delete(ns.interface_by_index, index)
		delete(ns.interface_by_name, name)
	}
}

func (m *net_namespace_main) interface_by_name(name string) (ns *net_namespace, intf *net_namespace_interface) {
	for _, s := range m.namespace_by_name {
		if i, ok := s.interface_by_name[name]; ok {
			ns, intf = s, i
			break
		}
	}
	return
}

func (ns *net_namespace) String() (s string) {
	s = ns.name
	if s == "" {
		s = "default-namespace"
	}
	return
}

type showNsMsg struct {
	Interface string `format:"%-30s"`
	Namespace string `format:"%s" align:"center"`
	NSID      string `format:"%s" align:"center"`
}
type showNsMsgs []showNsMsg

func (ns showNsMsgs) Less(i, j int) bool {
	if ns[i].Namespace == ns[j].Namespace {
		return ns[i].Interface < ns[j].Interface
	}
	return ns[i].Namespace < ns[j].Namespace
}
func (ns showNsMsgs) Swap(i, j int) { ns[i], ns[j] = ns[j], ns[i] }
func (ns showNsMsgs) Len() int      { return len(ns) }

func (m *netlink_main) show_net_namespaces(c cli.Commander, w cli.Writer, in *cli.Input) (err error) {
	ms := showNsMsgs{}
	for _, ns := range m.namespace_by_name {
		for _, intf := range ns.interface_by_index {
			x := showNsMsg{Namespace: ns.name, Interface: intf.name}
			if ns.nsid != -1 {
				x.NSID = fmt.Sprintf("%d", ns.nsid)
			}
			ms = append(ms, x)
		}
	}
	sort.Sort(ms)
	elib.TabulateWrite(w, ms)
	return
}

func (ns *net_namespace) allocate_sockets() (err error) {
	ns.tx_raw_socket_fd, err = syscall.Socket(syscall.AF_PACKET, syscall.SOCK_RAW, 0)
	if err == nil {
		ns.netlink_socket_fds[0], err = syscall.Socket(syscall.AF_NETLINK, syscall.SOCK_RAW, syscall.NETLINK_ROUTE)
	}
	if err == nil {
		ns.netlink_socket_fds[1], err = syscall.Socket(syscall.AF_NETLINK, syscall.SOCK_RAW, syscall.NETLINK_ROUTE)
	}
	return
}

func (ns *net_namespace) iomux_add() {
	if err := syscall.SetsockoptInt(ns.tx_raw_socket_fd, syscall.SOL_SOCKET, syscall.SO_SNDBUF, 1<<20); err != nil {
		panic(err)
	}
	ns.File.SetWriteOnly()
	ns.File.Fd = ns.tx_raw_socket_fd
	iomux.Add(ns)
}

func (m *net_namespace_main) max_n_namespace() uint { return uint(len(m.namespace_by_name)) }

func (ns *net_namespace) add(m *netlink_main) {
	// Allocate unique index for namespace.
	nm := &m.net_namespace_main
	ns.index = nm.namespace_pool.GetIndex()
	nm.namespace_pool.entries[ns.index] = ns

	// Loop until namespace sockets are allocated.
	time_start := time.Now()
	var (
		err               error
		first_setns_errno syscall.Errno
	)
	for {
		ns.m = nm
		if ns.ns_fd, err = m.fd_for_path(netnsDir, ns.name); err != nil {
			panic(err)
		}
		// First setns may return EINVAL until "ip netns add X" performs mount bind; so we need to retry.
		err, first_setns_errno = elib.WithNamespace(ns.ns_fd, m.default_namespace.ns_fd, syscall.CLONE_NEWNET, ns.allocate_sockets)
		if err == nil {
			break
		}
		if time.Since(time_start) > 10*time.Millisecond {
			panic(err)
		}
		syscall.Close(ns.ns_fd)
		ns.ns_fd = -1
		if first_setns_errno == syscall.EINVAL {
			time.Sleep(1 * time.Millisecond)
		}
	}
	ns.iomux_add()
	if err = ns.netlink_socket_pair.configure(ns.netlink_socket_fds[0], ns.netlink_socket_fds[1]); err != nil {
		panic(err)
	}
	ns.listen(m)
	ns.net_namespace_tx_node.init(nm)
}

func (ns *net_namespace) del(m *netlink_main) {
	ns.m.namespace_pool.PutIndex(ns.index)
	ns.m.namespace_pool.entries[ns.index] = nil
	ns.index = ^uint(0)

	iomux.Del(ns)
	if ns.ns_fd > 0 {
		syscall.Close(ns.ns_fd)
		ns.ns_fd = -1
	}
	if ns.Fd > 0 {
		syscall.Close(ns.Fd)
		ns.Fd = -1
	}
	ns.netlink_socket_pair.close()
}

func (ns *net_namespace) ErrorReady() (err error) {
	var v int
	v, err = syscall.GetsockoptInt(ns.Fd, syscall.SOL_SOCKET, syscall.SO_ERROR)
	if err == nil && v != 0 {
		err = syscall.Errno(v)
	}
	return
}
