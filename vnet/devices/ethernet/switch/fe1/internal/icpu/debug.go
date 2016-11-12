// Copyright 2016 Platina Systems, Inc. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

// +build debug

package icpu

import (
	. "github.com/platinasystems/go/vnet/devices/ethernet/switch/fe1/internal/debug"
	"unsafe"
)

func (r *u32) offset(regs *Regs) uint {
	return uint(uintptr(unsafe.Pointer(r)) - uintptr(unsafe.Pointer(regs)))
}

// Check memory map.
func init() {
	r := (*Regs)(unsafe.Pointer(&struct{ _ [32 << 10]byte }{}))
	CheckRegAddr("paxb[0]", r.paxb[0].clock_control.offset(r), 0x2000)
	CheckRegAddr("paxb[0].config_indirect_address", r.paxb[0].config_indirect_address.offset(r), 0x2120)
	CheckRegAddr("paxb[0].pcie_sys_msi_request", r.paxb[0].pcie_sys_msi_request.offset(r), 0x2340)
	CheckRegAddr("paxb[0].imap[0][0]", r.paxb[0].imap0[0][0].offset(r), 0x2c00)
	CheckRegAddr("paxb[0].iarr_2[0]", r.paxb[0].iarr_2[0].lower.offset(r), 0x2d00)
	CheckRegAddr("paxb[0].oarr_2[0]", r.paxb[0].oarr_2[0].lower.offset(r), 0x2d60)
	CheckRegAddr("paxb[0].mem_control", r.paxb[0].mem_control.offset(r), 0x2f00)
}
