// Copyright © 2015-2016 Platina Systems, Inc. All rights reserved.
// Use of this source code is governed by the GPL-2 license described in the
// LICENSE file.

// +build amd64 arm

// This is an example goes machine run as daemons w/in another distro.
package main

import (
	stdnet "net"

	"github.com/platinasystems/go/command"
	"github.com/platinasystems/go/goes"
	"github.com/platinasystems/go/goes/builtin"
	"github.com/platinasystems/go/goes/core"
	"github.com/platinasystems/go/goes/fs"
	"github.com/platinasystems/go/goes/kernel"
	"github.com/platinasystems/go/goes/machine"
	"github.com/platinasystems/go/goes/machine/start"
	"github.com/platinasystems/go/goes/net"
	"github.com/platinasystems/go/goes/net/nld"
	"github.com/platinasystems/go/goes/net/telnetd"
	"github.com/platinasystems/go/goes/redis"
	"github.com/platinasystems/go/goes/test"
)

func main() {
	command.Plot(builtin.New()...)
	command.Plot(core.New()...)
	command.Plot(fs.New()...)
	command.Plot(kernel.New()...)
	command.Plot(machine.New()...)
	command.Plot(net.New()...)
	command.Plot(redis.New()...)
	command.Plot(telnetd.New())
	command.Plot(test.New()...)
	command.Sort()
	start.Machine = "example"
	nld.Hook = func() error {
		itfs, err := stdnet.Interfaces()
		if err != nil {
			return nil
		}
		prefixes := make([]string, 0, len(itfs))
		for _, itf := range itfs {
			prefixes = append(prefixes, itf.Name+".")
		}
		nld.Prefixes = prefixes
		return nil
	}
	goes.Main()
}
