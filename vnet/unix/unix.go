// Copyright 2016 Platina Systems, Inc. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package unix

import (
	"github.com/platinasystems/go/elib/parse"
	"github.com/platinasystems/go/internal/netlink"
	"github.com/platinasystems/go/vnet"

	"regexp"
)

var packageIndex uint

type interface_filter struct {
	// Map of source string regexp to indication of whether or not matching interfaces should be terminated.
	s map[string]bool
	// As above but after compilation of regexps.
	m map[*regexp.Regexp]bool
}

func (f *interface_filter) add(s string, v bool) {
	if f.s == nil {
		f.s = make(map[string]bool)
	}
	f.s[s] = v
}
func AddInterfaceFilter(v *vnet.Vnet, s string, ok bool) { GetMain(v).interface_filter.add(s, ok) }

func (f *interface_filter) compile() (err error) {
	f.m = make(map[*regexp.Regexp]bool, len(f.s))
	for s, v := range f.s {
		var e *regexp.Regexp
		if e, err = regexp.Compile(s); err != nil {
			return
		}
		f.m[e] = v
	}
	return
}

func (f *interface_filter) run(s string, kind netlink.InterfaceKind) (ok bool) {
	if len(f.m) != len(f.s) {
		err := f.compile()
		if err != nil {
			panic(err)
		}
	}
	for e, v := range f.m {
		if e.MatchString(s) {
			ok = v
			return
		}
	}
	switch kind {
	case netlink.InterfaceKindDummy, netlink.InterfaceKindTun, netlink.InterfaceKindVeth, netlink.InterfaceKindVlan:
		ok = true
	}
	return
}

type Main struct {
	vnet.Package
	v               *vnet.Vnet
	verbose_netlink bool
	interface_filter
	net_namespace_main
	netlink_main
	tuntap_main
	vnet_tun_main
	Config
}

func GetMain(v *vnet.Vnet) *Main { return v.GetPackage(packageIndex).(*Main) }

type Config struct {
	RxInjectNodeName string
}

func Init(v *vnet.Vnet, cf Config) {
	m := &Main{}
	m.v = v
	m.Config = cf
	if false {
		m.tuntap_main.Init(v)
	}
	m.netlink_main.Init(m)
	if false {
		m.vnet_tun_main.init(m)
	}
	packageIndex = v.AddPackage("unix", m)
}

func (m *Main) Configure(in *parse.Input) {
	for !in.End() {
		var s string
		switch {
		case in.Parse("mtu %d", &m.mtuBytes):
		case in.Parse("verbose-netlink"):
			m.verbose_netlink = true
		case in.Parse("filter-accept %s", &s):
			m.interface_filter.add(s, true)
		case in.Parse("filter-reject %s", &s):
			m.interface_filter.add(s, false)
		default:
			in.ParseError()
		}
	}
}
