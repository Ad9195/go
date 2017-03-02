// Copyright © 2015-2016 Platina Systems, Inc. All rights reserved.
// Use of this source code is governed by the GPL-2 license described in the
// LICENSE file.

// Package fsp provides access to the power supply unit

package qsfp

import (
	"net"
	"net/http"
	"net/rpc"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/platinasystems/go/internal/goes"
	"github.com/platinasystems/go/internal/log"
	"github.com/platinasystems/go/internal/redis/publisher"
)

const Name = "qsfp"

type I2cDev struct {
	Bus       int
	Addr      int
	MuxBus    int
	MuxAddr   int
	MuxValue  int
	MuxBus2   int
	MuxAddr2  int
	MuxValue2 int
}

var Vdev [32]I2cDev

var VpageByKey map[string]uint8

type cmd struct {
	stop  chan struct{}
	pub   *publisher.Publisher
	last  map[string]float64
	lasts map[string]string
	lastu map[string]uint8
}

func New() *cmd { return new(cmd) }

func (*cmd) Kind() goes.Kind { return goes.Daemon }
func (*cmd) String() string  { return Name }
func (*cmd) Usage() string   { return Name }

func (cmd *cmd) Main(...string) error {
	var si syscall.Sysinfo_t
	var err error

	qsfpPres := new(QsfpPres)
	rpc.Register(qsfpPres)
	rpc.HandleHTTP()
	l, e := net.Listen("tcp", ":1232")
	if e != nil {
		log.Print("listen ERROR QsfpPres:", e)
	}
	log.Print("listen QsfpPres OKAY")
	go http.Serve(l, nil)

	cmd.stop = make(chan struct{})
	cmd.last = make(map[string]float64)
	cmd.lasts = make(map[string]string)
	cmd.lastu = make(map[string]uint8)

	if cmd.pub, err = publisher.New(); err != nil {
		return err
	}

	if err = syscall.Sysinfo(&si); err != nil {
		return err
	}

	//	if err = cmd.update(); err != nil {
	//		close(cmd.stop)
	//		return err
	//	}
	t := time.NewTicker(10 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-cmd.stop:
			return nil
		case <-t.C:
			if err = cmd.update(); err != nil {
				close(cmd.stop)
				return err
			}
		}
	}
	return nil
}

func (cmd *cmd) Close() error {
	close(cmd.stop)
	return nil
}

func (cmd *cmd) update() error {
	stopped := readStopped()
	if stopped == 1 {
		return nil
	}

	if l.Present[0] == 0 {
		//add logic here to conditiionally do the read and publish
		//l will change automatically
	}
	if l.Present[1] == 0 {
		//add logic here to conditiionally do the read and publish
		//l will change automatically
	}

	for k, i := range VpageByKey {
		if strings.Contains(k, "compliance") {
			v := Vdev[i].Compliance()
			if v != cmd.lasts[k] {
				cmd.pub.Print(k, ": ", v)
				cmd.lasts[k] = v
			}
		}
		if strings.Contains(k, "vendor") {
			v := Vdev[i].Vendor()
			if v != cmd.lasts[k] {
				cmd.pub.Print(k, ": ", v)
				cmd.lasts[k] = v
			}
		}
		if strings.Contains(k, "partnumber") {
			v := Vdev[i].PN()
			if v != cmd.lasts[k] {
				cmd.pub.Print(k, ": ", v)
				cmd.lasts[k] = v
			}
		}
		if strings.Contains(k, "serialnumber") {
			v := Vdev[i].SN()
			if v != cmd.lasts[k] {
				cmd.pub.Print(k, ": ", v)
				cmd.lasts[k] = v
			}
		}
	}
	return nil
}

func (h *I2cDev) Compliance() string {
	r := getRegs()

	r.SpecCompliance.get(h)
	DoI2cRpc()
	cp := s[2].D[0]

	r.ExtSpecCompliance.get(h)
	DoI2cRpc()
	ecp := s[2].D[0]

	var t string
	if (cp & 0x80) != 0x80 {
		t = specComplianceValues[cp]
	} else {
		t = extSpecComplianceValues[ecp]
	}
	return t
}

func (h *I2cDev) Vendor() string {
	r := getRegs()
	r.VendorName.get(h, 16)
	DoI2cRpc()
	t := string(s[2].D[1:16])

	return t
}

func (h *I2cDev) PN() string {
	r := getRegs()
	r.VendorPN.get(h, 16)
	DoI2cRpc()
	t := string(s[2].D[1:16])

	return t
}

func (h *I2cDev) SN() string {
	r := getRegs()
	r.VendorSN.get(h, 16)
	DoI2cRpc()
	t := string(s[2].D[1:16])

	return t
}

type QsfpI2cGpio struct {
	Present [2]uint16
}
type X struct {
	Resp uint32
}
type QsfpPres int

var l = QsfpI2cGpio{[2]uint16{0xffff, 0xffff}}
var mutex = &sync.Mutex{}

func (t *QsfpPres) Write(g *QsfpI2cGpio, f *X) error {
	mutex.Lock()
	defer mutex.Unlock()

	l = *g
	f.Resp = 0
	return nil
}
