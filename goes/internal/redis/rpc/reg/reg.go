// Copyright © 2015-2016 Platina Systems, Inc. All rights reserved.
// Use of this source code is governed by the GPL-2 license described in the
// LICENSE file.

// Package reg provides an RPC to register redis handlers.
package reg

import (
	netrpc "net/rpc"

	"github.com/platinasystems/go/goes/internal/redis/rpc"
	"github.com/platinasystems/go/goes/internal/redis/rpc/args"
	"github.com/platinasystems/go/goes/sockfile"
)

type Reg struct {
	Srvr     *sockfile.RpcServer
	assign   Assigner
	unassign Unassigner
}

type Assigner func(string, interface{}) error
type Unassigner func(string) error

// e.g. name, "redis-reg"
func New(name string, assign Assigner, unassign Unassigner) (*Reg, error) {
	srvr, err := sockfile.NewRpcServer("redis-reg")
	if err != nil {
		return nil, err
	}
	reg := &Reg{srvr, assign, unassign}
	netrpc.Register(reg)
	return reg, nil
}

// Assign an RPC handler for the given redis key.
func (reg *Reg) Assign(a args.Assign, _ *struct{}) error {
	return reg.assign(a.Key, &rpc.Rpc{a.File, a.Name})
}

// Assign the handler for the given redis key.
func (reg *Reg) Unassign(a args.Unassign, _ *struct{}) error {
	return reg.unassign(a.Key)
}
