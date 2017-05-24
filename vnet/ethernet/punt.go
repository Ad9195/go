// Copyright 2016 Platina Systems, Inc. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package ethernet

import (
	"github.com/platinasystems/go/vnet"
)

const (
	punt_2tag_next_punt uint = iota
	punt_2tag_next_error
)
const (
	punt_2tag_error_none uint = iota
	punt_2tag_error_not_double_tagged
	punt_2tag_error_unknown_disposition
)

type punt_packet_disposition struct {
	o            vnet.RefOpaque
	next         uint32
	data_advance int32
}

//go:generate gentemplate -d Package=ethernet -id punt_packet_disposition -d PoolType=punt_packet_disposition_pool -d Type=punt_packet_disposition -d Data=dispositions github.com/platinasystems/go/elib/pool.tmpl

type DoubleTaggedPuntNode struct {
	vnet.InOutNode
	punt_packet_disposition_pool
}

func (n *DoubleTaggedPuntNode) AddDisposition(next string, o vnet.RefOpaque, data_advance int32) (i uint32) {
	i = uint32(n.punt_packet_disposition_pool.GetIndex())
	d := &n.dispositions[i]
	d.o = o
	d.next = uint32(n.Vnet.AddNamedNext(n, next))
	d.data_advance = data_advance
	return
}

func (n *DoubleTaggedPuntNode) DelDisposition(i uint32) {
	n.punt_packet_disposition_pool.PutIndex(uint(i))
}

// Ethernet header followed by is 2 vlan tags.
// Packet looks like this DST-ETHERNET SRC-ETHERNET 0x8100 TAG0 0x8100 TAG1 ETHERNET-TYPE
type header_no_type struct {
	dst, src Address
}

const (
	sizeof_header_no_type = 12
	sizeof_double_tag     = 8
)

func (n *DoubleTaggedPuntNode) punt_x1(r0 *vnet.Ref) (next0 uint) {
	p0 := *(*vnet.Uint64)(r0.DataOffset(sizeof_header_no_type))

	var t = (vnet.Uint64(TYPE_VLAN)<<48 | vnet.Uint64(TYPE_VLAN)<<16).FromHost()
	var m = (vnet.Uint64(0xffff)<<48 | vnet.Uint64(0xffff)<<16).FromHost()

	error0 := punt_2tag_error_none
	if p0&m != t {
		error0 = punt_2tag_error_not_double_tagged
	}

	o0 := p0 &^ m
	if vnet.HostIsNetworkByteOrder() {
		o0 |= p0 >> 16
	} else {
		o0 |= p0 >> 48
	}

	di0 := uint32(o0)

	if di0 >= uint32(n.punt_packet_disposition_pool.Len()) {
		error0 = punt_2tag_error_unknown_disposition
		di0 = 0
	}

	d0 := &n.dispositions[di0]

	r0.RefOpaque = d0.o

	n.SetError(r0, error0)

	next0 = uint(d0.next)
	if error0 != punt_2tag_error_none {
		next0 = punt_2tag_next_error
	}

	// Remove double tag.  After this call packet is untagged.
	*(*header_no_type)(r0.DataOffset(sizeof_double_tag)) = *(*header_no_type)(r0.DataOffset(0))

	r0.Advance(sizeof_double_tag + int(d0.data_advance))

	return
}

func (n *DoubleTaggedPuntNode) punt_x2(r0, r1 *vnet.Ref) (next0, next1 uint) {
	p0 := *(*vnet.Uint64)(r0.DataOffset(sizeof_header_no_type))
	p1 := *(*vnet.Uint64)(r1.DataOffset(sizeof_header_no_type))

	var t = (vnet.Uint64(TYPE_VLAN)<<48 | vnet.Uint64(TYPE_VLAN)<<16).FromHost()
	var m = (vnet.Uint64(0xffff)<<48 | vnet.Uint64(0xffff)<<16).FromHost()

	error0, error1 := punt_2tag_error_none, punt_2tag_error_none
	if p0&m != t {
		error0 = punt_2tag_error_not_double_tagged
	}
	if p1&m != t {
		error1 = punt_2tag_error_not_double_tagged
	}

	o0, o1 := p0&^m, p1&^m
	if vnet.HostIsNetworkByteOrder() {
		o0 |= p0 >> 16
		o1 |= p1 >> 16
	} else {
		o0 |= p0 >> 48
		o1 |= p1 >> 48
	}

	di0, di1 := uint32(o0), uint32(o1)

	if di0 >= uint32(n.punt_packet_disposition_pool.Len()) {
		error0 = punt_2tag_error_unknown_disposition
		di0 = 0
	}
	if di1 >= uint32(n.punt_packet_disposition_pool.Len()) {
		error1 = punt_2tag_error_unknown_disposition
		di1 = 0
	}

	d0, d1 := &n.dispositions[di0], &n.dispositions[di1]

	r0.RefOpaque = d0.o
	r1.RefOpaque = d1.o

	n.SetError(r0, error0)
	n.SetError(r1, error1)

	next0, next1 = uint(d0.next), uint(d1.next)
	if error0 != punt_2tag_error_none {
		next0 = punt_2tag_next_error
	}
	if error1 != punt_2tag_error_none {
		next1 = punt_2tag_next_error
	}

	// Remove double tag.  After this call packet is untagged.
	*(*header_no_type)(r0.DataOffset(sizeof_double_tag)) = *(*header_no_type)(r0.DataOffset(0))
	*(*header_no_type)(r1.DataOffset(sizeof_double_tag)) = *(*header_no_type)(r1.DataOffset(0))

	r0.Advance(sizeof_double_tag + int(d0.data_advance))
	r1.Advance(sizeof_double_tag + int(d0.data_advance))

	return
}

func (n *DoubleTaggedPuntNode) Init(v *vnet.Vnet, name string) {
	n.Next = []string{
		punt_2tag_next_error: "error",
		punt_2tag_next_punt:  "punt",
	}
	n.Errors = []string{
		punt_2tag_error_none:                "no error",
		punt_2tag_error_not_double_tagged:   "not double vlan tagged",
		punt_2tag_error_unknown_disposition: "unknown packet disposition",
	}
	v.RegisterInOutNode(n, name+"-double-tagged-punt")
	n.AddDisposition("punt", vnet.RefOpaque{}, 0)
}

func (n *DoubleTaggedPuntNode) NodeInput(in *vnet.RefIn, o *vnet.RefOut) {
	q := n.GetEnqueue(in)
	i, n_left := in.Range()

	for n_left >= 2 {
		r0, r1 := in.Get2(i)
		x0, x1 := n.punt_x2(r0, r1)
		q.Put2(r0, r1, x0, x1)
		n_left -= 2
		i += 2
	}

	for n_left >= 1 {
		r0 := in.Get1(i)
		x0 := n.punt_x1(r0)
		q.Put1(r0, x0)
		n_left -= 1
		i += 1
	}
}

type inject_packet_disposition struct {
	next uint32
	tags [2]VlanTag
}

//go:generate gentemplate -d Package=ethernet -id inject_packet_disposition -d VecType=inject_packet_disposition_vec -d Type=inject_packet_disposition github.com/platinasystems/go/elib/vec.tmpl

type DoubleTaggedInjectNode struct {
	vnet.InOutNode
	disposition_by_si inject_packet_disposition_vec
}

func (n *DoubleTaggedInjectNode) AddDisposition(next string, si vnet.Si, tags [2]VlanTag) {
	d := &n.disposition_by_si[si]
	d.tags = tags
	d.next = uint32(n.Vnet.AddNamedNext(n, next))
	return
}

func (n *DoubleTaggedInjectNode) sw_if_add_del(v *vnet.Vnet, si vnet.Si, isUp bool) (err error) {
	zero := inject_packet_disposition{next: uint32(inject_2tag_next_error)}
	n.disposition_by_si.ValidateInit(uint(si), zero)
	return
}

func (n *DoubleTaggedInjectNode) inject_x1(r0 *vnet.Ref) (next0 uint) {
	var t = (vnet.Uint64(TYPE_VLAN)<<48 | vnet.Uint64(TYPE_VLAN)<<16).FromHost()

	d0 := &n.disposition_by_si[r0.Si]

	o0 := t
	if vnet.HostIsNetworkByteOrder() {
		o0 |= vnet.Uint64(d0.tags[0]) | vnet.Uint64(d0.tags[1])<<32
	} else {
		o0 |= vnet.Uint64(d0.tags[0])<<16 | vnet.Uint64(d0.tags[1])<<48
	}

	h0 := *(*header_no_type)(r0.DataOffset(0))

	r0.Advance(-sizeof_double_tag)

	*(*vnet.Uint64)(r0.DataOffset(sizeof_header_no_type)) = o0

	*(*header_no_type)(r0.DataOffset(0)) = h0

	next0 = uint(d0.next)

	return
}
func (n *DoubleTaggedInjectNode) inject_x2(r0, r1 *vnet.Ref) (next0, next1 uint) {
	var t = (vnet.Uint64(TYPE_VLAN)<<48 | vnet.Uint64(TYPE_VLAN)<<16).FromHost()

	d0, d1 := &n.disposition_by_si[r0.Si], &n.disposition_by_si[r1.Si]

	o0, o1 := t, t
	if vnet.HostIsNetworkByteOrder() {
		o0 |= vnet.Uint64(d0.tags[0]) | vnet.Uint64(d0.tags[1])<<32
		o1 |= vnet.Uint64(d1.tags[0]) | vnet.Uint64(d1.tags[1])<<32
	} else {
		o0 |= vnet.Uint64(d0.tags[0])<<16 | vnet.Uint64(d0.tags[1])<<48
		o1 |= vnet.Uint64(d1.tags[0])<<16 | vnet.Uint64(d1.tags[1])<<48
	}

	h0, h1 := *(*header_no_type)(r0.DataOffset(0)), *(*header_no_type)(r1.DataOffset(0))

	r0.Advance(-sizeof_double_tag)
	r1.Advance(-sizeof_double_tag)

	*(*vnet.Uint64)(r0.DataOffset(sizeof_header_no_type)) = o0
	*(*vnet.Uint64)(r1.DataOffset(sizeof_header_no_type)) = o1

	*(*header_no_type)(r0.DataOffset(0)) = h0
	*(*header_no_type)(r1.DataOffset(0)) = h1

	next0 = uint(d0.next)
	next1 = uint(d1.next)

	return
}

const (
	inject_2tag_next_error uint = iota
)
const (
	inject_2tag_error_none uint = iota
	inject_2tag_error_unknown_interface
)

func (n *DoubleTaggedInjectNode) Init(v *vnet.Vnet, name string) {
	n.Next = []string{
		inject_2tag_next_error: "error",
	}
	n.Errors = []string{
		inject_2tag_error_none:              "no error",
		inject_2tag_error_unknown_interface: "unknown interface",
	}
	v.RegisterInOutNode(n, name+"-double-tagged-inject")
	v.RegisterSwIfAddDelHook(n.sw_if_add_del)
}

func (n *DoubleTaggedInjectNode) NodeInput(in *vnet.RefIn, o *vnet.RefOut) {
	q := n.GetEnqueue(in)
	i, n_left := in.Range()

	for n_left >= 2 {
		r0, r1 := in.Get2(i)
		x0, x1 := n.inject_x2(r0, r1)
		q.Put2(r0, r1, x0, x1)
		n_left -= 2
		i += 2
	}

	for n_left >= 1 {
		r0 := in.Get1(i)
		x0 := n.inject_x1(r0)
		q.Put1(r0, x0)
		n_left -= 1
		i += 1
	}
}

type DoubleTaggedPuntInjectNodes struct {
	Punt   DoubleTaggedPuntNode
	Inject DoubleTaggedInjectNode
}

func (n *DoubleTaggedPuntInjectNodes) Init(v *vnet.Vnet, name string) {
	n.Punt.Init(v, name)
	n.Inject.Init(v, name)
}
