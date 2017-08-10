// Copyright 2016 Platina Systems, Inc. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package unix

import (
	"github.com/platinasystems/go/vnet"
	"github.com/platinasystems/go/vnet/ethernet"

	"unsafe"
)

type vnet_tun_main struct {
	m                    *Main
	linux_interface_name string
	vnet.SwInterfaceType
}

// Vnet name for interface (includes namespace); linux name is always "vnet" in each namespace.
func (m *vnet_tun_main) SwInterfaceName(v *vnet.Vnet, s *vnet.SwIf) string {
	ns := m.m.namespace_pool.entries[s.GetId()]
	return m.linux_interface_name + "-" + ns.name
}

func (m *vnet_tun_main) init(um *Main) {
	m.m = um
	m.linux_interface_name = "vnet"
	um.v.RegisterSwInterfaceType(m)
}

func (m *vnet_tun_main) si_is_vnet_tun(si vnet.Si) bool {
	return si.Kind(m.m.v) == m.SwIfKind
}
func (m *vnet_tun_main) SwInterfaceSetRewrite(r *vnet.Rewrite, si vnet.Si, noder vnet.Noder, typ vnet.PacketType) {
	r.Si = si
	n := noder.GetNode()
	r.NodeIndex = uint32(n.Index())
	r.NextIndex = ^uint32(0)
	r.MaxL3PacketSize = ^uint16(0)
	var h ethernet.Header
	h.Type.SetPacketType(typ)
	r.ResetData()
	r.AddData(unsafe.Pointer(&h), ethernet.SizeofHeader)
}
func (m *vnet_tun_main) SwInterfaceRewriteString(v *vnet.Vnet, r *vnet.Rewrite) []string {
	return ethernet.FormatRewrite(v, r)
}

// Sort interfaces by name of corresponding namespace.
func (m *vnet_tun_main) SwInterfaceLessThan(v *vnet.Vnet, a, b *vnet.SwIf) bool {
	nsa, nsb := m.m.namespace_pool.entries[a.GetId()], m.m.namespace_pool.entries[b.GetId()]
	return nsa.name < nsb.name
}

func (m *vnet_tun_main) create_tun(ns *net_namespace) (intf *tuntap_interface) {
	si := m.m.v.NewSwIf(m.SwIfKind, vnet.IfId(ns.index))
	intf = m.m.vnet_tuntap_interface_by_si[si]
	intf.namespace = ns
	ns.vnet_tun_interface = intf
	return
}

func IsVnetTun(v *vnet.Vnet, si vnet.Si) bool {
	return GetMain(v).si_is_vnet_tun(si)
}
