// Copyright © 2015-2016 Platina Systems, Inc. All rights reserved.
// Use of this source code is governed by the GPL-2 license described in the
// LICENSE file.

package panicd

import (
	"strings"

	"github.com/platinasystems/go/internal/goes"
)

const Name = "panicd"

type cmd struct{}

func New() cmd { return cmd{} }

func (cmd) Kind() goes.Kind { return goes.Daemon }
func (cmd) String() string  { return Name }
func (cmd) Usage() string   { return Name + " [MESSAGE]..." }

func (cmd) Main(args ...string) error {
	msg := "---"
	if len(args) > 0 {
		msg = strings.Join(args, " ")
	}
	panic(msg)
	return nil
}

func (cmd) Apropos() map[string]string {
	return map[string]string{
		"en_US.UTF-8": "test daemon error log",
	}
}

func (cmd) Man() map[string]string {
	return map[string]string{
		"en_US.UTF-8": `NAME
	panicd - test daemon error log

SYNOPSIS
	panicd [MESSAGE]...

DESCRIPTION
	Print the given or default message to klog or syslog.`,
	}
}
