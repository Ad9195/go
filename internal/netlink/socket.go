// Copyright © 2015-2016 Platina Systems, Inc. All rights reserved.
// Use of this source code is governed by the GPL-2 license described in the
// LICENSE file.

package netlink

import (
	"fmt"
	"io"
	"os"
	"sync"
	"syscall"
	"unsafe"
)

var (
	DefaultGroups = []MulticastGroup{
		RTNLGRP_LINK,
		RTNLGRP_NEIGH,
		RTNLGRP_IPV4_IFADDR,
		RTNLGRP_IPV4_ROUTE,
		RTNLGRP_IPV4_MROUTE,
		RTNLGRP_IPV6_IFADDR,
		RTNLGRP_IPV6_ROUTE,
		RTNLGRP_IPV6_MROUTE,
		RTNLGRP_NSID,
	}
	DefaultListenReqs = []ListenReq{
		{RTM_GETNSID, AF_UNSPEC},
		{RTM_GETLINK, AF_PACKET},
		{RTM_GETADDR, AF_INET},
		{RTM_GETADDR, AF_INET6},
		{RTM_GETNEIGH, AF_INET},
		{RTM_GETNEIGH, AF_INET6},
		{RTM_GETROUTE, AF_INET},
		{RTM_GETROUTE, AF_INET6},
	}
	NoopListenReq = ListenReq{NLMSG_NOOP, AF_UNSPEC}
)

// Zero means use default value.
type SocketConfig struct {
	RxBytes int
	TxBytes int

	RxMessages int
	TxMessages int

	DontListenAllNsid bool

	Groups []MulticastGroup
}

type Handler func(Message) error

type ListenReq struct {
	MsgType
	AddressFamily
}

type Socket struct {
	once sync.Once
	fd   int
	addr *syscall.SockaddrNetlink
	Rx   <-chan Message
	rx   chan<- Message
	Tx   chan<- Message
	tx   <-chan Message
	SocketConfig
}

func New(groups ...MulticastGroup) (*Socket, error) {
	return NewWithConfig(SocketConfig{Groups: groups})
}

func NewWithConfig(cf SocketConfig) (s *Socket, err error) {
	fd, err := syscall.Socket(syscall.AF_NETLINK, syscall.SOCK_RAW,
		syscall.NETLINK_ROUTE)
	if err != nil {
		err = os.NewSyscallError("socket", err)
		return
	}

	if cf.RxMessages == 0 {
		cf.RxMessages = DefaultMessages
	}
	rx := make(chan Message, cf.RxMessages)

	if cf.TxMessages == 0 {
		cf.TxMessages = DefaultMessages
	}
	tx := make(chan Message, cf.TxMessages)

	if len(cf.Groups) == 0 {
		cf.Groups = DefaultGroups
	}

	s = &Socket{
		fd: fd,

		Rx: rx,
		rx: rx,
		Tx: tx,
		tx: tx,

		SocketConfig: cf,
	}

	defer func() {
		if err != nil && fd > 0 {
			syscall.Close(fd)
			if s != nil {
				if s.rx != nil {
					close(s.rx)
				}
				if s.Tx != nil {
					close(s.Tx)
				}
				s.addr = nil
				s = nil
			}
		}
	}()

	addr := syscall.SockaddrNetlink{
		Family: uint16(AF_NETLINK),
	}

	for _, group := range cf.Groups {
		if group != NOOP_RTNLGRP {
			addr.Groups |= 1 << group
		}
	}

	err = os.NewSyscallError("bind", syscall.Bind(s.fd, &addr))
	if err != nil {
		return
	}

	xaddr, err := syscall.Getsockname(s.fd)
	err = os.NewSyscallError("Getsockname", err)
	if err != nil {
		return
	}
	s.addr = xaddr.(*syscall.SockaddrNetlink)

	// Increase socket buffering.
	if s.RxBytes != 0 {
		err = os.NewSyscallError("setsockopt SO_RCVBUF",
			syscall.SetsockoptInt(s.fd, syscall.SOL_SOCKET,
				syscall.SO_RCVBUF, s.RxBytes))
		if err != nil {
			return
		}
		// Verify buffer size is at least as large as requested.
		var v int
		v, err = syscall.GetsockoptInt(s.fd, syscall.SOL_SOCKET,
			syscall.SO_RCVBUF)
		if err != nil {
			return
		} else if v < s.RxBytes {
			err = fmt.Errorf(`
SO_RCVBUF truncated to %d bytes; run: sysctl -w net.core.rmem_max=%d`[1:],
				v, s.RxBytes)
			return
		}
	}

	if s.TxBytes != 0 {
		err = os.NewSyscallError("setsockopt SO_SNDBUF",
			syscall.SetsockoptInt(s.fd, syscall.SOL_SOCKET,
				syscall.SO_SNDBUF, s.TxBytes))
		if err != nil {
			return
		}
		// Verify buffer size is at least as large as requested.
		var v int
		v, err = syscall.GetsockoptInt(s.fd, syscall.SOL_SOCKET,
			syscall.SO_SNDBUF)
		if err != nil {
			return
		} else if v < s.TxBytes {
			err = fmt.Errorf(`
SO_SNDBUF truncated to %d bytes; run: sysctl -w net.core.wmem_max=%d`[1:],
				v, s.TxBytes)
			return
		}
	}

	if !s.DontListenAllNsid {
		err = os.NewSyscallError("setsockopt NETLINK_LISTEN_ALL_NSID",
			syscall.SetsockoptInt(s.fd, SOL_NETLINK,
				NETLINK_LISTEN_ALL_NSID, 1))
		if err != nil {
			return
		}
	}

	go s.gorx()
	go s.gotx()

	return
}

func (s *Socket) Close() error {
	err := syscall.Close(s.fd)
	s.fd = -1
	return err
}

func (s *Socket) GetlinkReq(nsid int) {
	req := NewGenMessage()
	req.nsid = nsid
	req.Type = RTM_GETLINK
	req.Flags = NLM_F_REQUEST | NLM_F_MATCH
	req.AddressFamily = AF_UNSPEC
	s.Tx <- req
}

// The Listen handler is for messages that we receive while waiting for the
// DONE or ERROR acknowledgement to each dump request.
func (s *Socket) Listen(handler Handler, reqs ...ListenReq) (err error) {
	if len(reqs) == 0 {
		reqs = DefaultListenReqs
	}
	for _, r := range reqs {
		if r.MsgType == NLMSG_NOOP {
			continue
		}
		for tries := 1; true; tries++ {
			msg := NewGenMessage()
			msg.Type = r.MsgType
			msg.Flags = NLM_F_REQUEST | NLM_F_DUMP
			msg.AddressFamily = r.AddressFamily
			s.Tx <- msg
			err := s.RxUntilDone(handler)
			if err == nil {
				break
			}
			if tries >= 5 {
				return err
			}
		}
	}
	return nil
}

func (s *Socket) RxUntilDone(handler Handler) (err error) {
	for msg := range s.Rx {
		switch msg.MsgType() {
		case NLMSG_ERROR:
			e := msg.(*ErrorMessage)
			if e.Errno != 0 {
				err = syscall.Errno(-e.Errno)
			}
			msg.Close()
			return
		case NLMSG_DONE:
			msg.Close()
			return
		default:
			err = handler(msg)
			if err != nil {
				return
			}
		}
	}
	return
}

func (s *Socket) gorx() {
	buf := make([]byte, 16*PageSz)
	oob := make([]byte, 2*PageSz)

	hasNsid := func(scm syscall.SocketControlMessage) bool {
		return scm.Header.Level == SOL_NETLINK &&
			scm.Header.Type == NETLINK_LISTEN_ALL_NSID
	}
	getNsid := func(scm syscall.SocketControlMessage) int {
		return *(*int)(unsafe.Pointer(&scm.Data[0]))
	}

	// Round the length of a netlink message up to align it properly.
	messageAlignLen := func(l int) int {
		return (l + NLMSG_ALIGNTO - 1) & ^(NLMSG_ALIGNTO - 1)
	}

	for {
		nsid := DefaultNsid

		n, noob, _, _, err := syscall.Recvmsg(s.fd, buf, oob, 0)
		if err != nil {
			if err != io.EOF && s.fd > 0 {
				fmt.Fprintln(os.Stderr, "Recv:", err)
			}
			break
		}

		if noob > 0 {
			scms, err :=
				syscall.ParseSocketControlMessage(oob[:noob])
			if err != nil {
				panic(err)
			}
			for _, scm := range scms {
				if hasNsid(scm) {
					nsid = getNsid(scm)
				}
			}
		}

		for i, l := 0, 0; i < n; i += l {
			if i+SizeofHeader > n {
				panic("incomplete header")
			}
			h := (*Header)(unsafe.Pointer(&buf[i]))
			l = messageAlignLen(int(h.Len))
			var msg Message
			switch h.Type {
			case NLMSG_NOOP:
				msg = NewNoopMessage()
			case NLMSG_ERROR:
				msg = NewErrorMessage()
			case NLMSG_DONE:
				msg = NewDoneMessage()
			case RTM_NEWLINK, RTM_DELLINK, RTM_GETLINK, RTM_SETLINK:
				msg = NewIfInfoMessage()
			case RTM_NEWADDR, RTM_DELADDR, RTM_GETADDR:
				msg = NewIfAddrMessage()
			case RTM_NEWROUTE, RTM_DELROUTE, RTM_GETROUTE:
				msg = NewRouteMessage()
			case RTM_NEWNEIGH, RTM_DELNEIGH, RTM_GETNEIGH:
				msg = NewNeighborMessage()
			case RTM_NEWNSID, RTM_DELNSID, RTM_GETNSID:
				msg = NewNetnsMessage()
			}
			if msg != nil {
				*msg.Nsid() = nsid
				_, err = msg.Write(buf[i : i+l])
				if err != nil {
					errno, ok := err.(syscall.Errno)
					if !ok {
						errno = syscall.EINVAL
					}
					msg.Close()
					e := NewErrorMessage()
					e.Errormsg.Errno = -int32(errno)
					e.Errormsg.Req = *h
					msg = e
				}
				if false {
					fmt.Fprint(os.Stderr, "Rx: ", msg)
				}
				s.rx <- msg
			}
		}
	}
	close(s.rx)
	s.rx = nil
}

func (s *Socket) gotx() {
	seq := uint32(1)
	buf := make([]byte, 16*PageSz)
	oob := make([]byte, PageSz)
	h := (*Header)(unsafe.Pointer(&buf[0]))
	scm := (*syscall.SocketControlMessage)(unsafe.Pointer(&oob[0]))
	scmNsid := (*int)(unsafe.Pointer(&oob[syscall.SizeofCmsghdr]))
	const noob = syscall.SizeofCmsghdr + SizeofInt

	for msg := range s.tx {
		n, err := msg.Read(buf)
		if err != nil {
			s.once.Do(func() {
				fmt.Fprintln(os.Stderr, "Read:", msg,
					"ERROR:", err)
			})
			msg.Close()
			continue
		}
		nsid := *msg.Nsid()
		msg.Close()
		if h.Flags == 0 {
			h.Flags = NLM_F_REQUEST
		}
		if h.Pid == 0 {
			h.Pid = s.addr.Pid
		}
		if h.Sequence == 0 {
			h.Sequence = seq
			seq++
		}
		h.Len = uint32(n)
		if nsid != DefaultNsid {
			scm.Header.Level = SOL_NETLINK
			scm.Header.Type = NETLINK_LISTEN_ALL_NSID
			*scmNsid = nsid
			scm.Header.SetLen(noob)
			err = syscall.Sendmsg(s.fd, buf[:n], oob[:noob],
				s.addr, 0)
		} else {
			_, err = syscall.Write(s.fd, buf[:n])
		}
		if err != nil {
			fmt.Fprintln(os.Stderr, "Send:", msg, "ERROR:", err)
			break
		}
	}
}
