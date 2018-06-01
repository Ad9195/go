// Copyright © 2015-2018 Platina Systems, Inc. All rights reserved.
// Use of this source code is governed by the GPL-2 license described in the
// LICENSE file.

package bootd

const (
	Register       = "register"
	NumClients     = "getnumclients"
	ClientData     = "getclientdata"
	ClientBootData = "getclientbootdata"
	Script         = "getscript"
	Binary         = "getbinary"
	DumpVars       = "dumpvars"
	Dashboard      = "dashboard"
	Dashboard2     = "dashboard2"
)
const (
	BootStateNotRegistered = iota
	BootStateRegistered
	BootStateBooting
	BootStateUp
	BootStateInstalling
	BootStateIntstallFailed
	BootStateRebooting
)
const (
	InstallStateFactory = iota
	InstallStateInProgress
	InstallStateInstalled
	InstallStateInstallFail
	InstallStateFactoryInProgress
	InstallStateFactoryFailed
)
const (
	Debian = iota
)
const (
	RegReplyRegistered = iota
	RegReplyNotRegistered
)
const (
	ScriptBootLatest = iota
	ScriptBootKnownGood
	ScriptInstallDebian
)
const (
	BootReplyNormal = iota
	BootReplyRunGoesScript
	BootReplyExecUsermode
	BootReplyExecKernel
	BootReplyReflashAndReboot
)

type BootcConfig struct {
	Install         bool
	BootSda1        bool
	BootSda6Cnt     int
	EraseSda6       bool
	IAmMaster       bool
	MyIpAddr        string
	MyGateway       string
	MyNetmask       string
	MasterAddresses []string
	ReInstallK      string
	ReInstallI      string
	ReInstallC      string
	Sda1K           string
	Sda1I           string
	Sda1C           string
	Sda6K           string
	Sda6I           string
	Sda6C           string
	InitScript      bool
	InitScriptName  string
	ISO1Name        string
	ISO1Desc        string
	ISO2Name        string
	ISO2Desc        string
	ISOlastUsed     int
	PostInstall     bool
}

type Client struct {
	Unit           int
	Name           string
	Machine        string
	MacAddr        string
	IpAddr         string
	IpGWay         string
	IpMask         string
	BootState      int
	InstallState   int
	AutoInstall    bool
	CertPresent    bool
	DistroType     int
	TimeRegistered string
	TimeInstalled  string
	InstallCounter int
	LastISOname    string
	LastISOdesc    string
}

type RegReq struct {
	Mac string
	IP  string
}

type RegReply struct {
	Reply   int
	TorName string
	Error   error
}

type NumClntReply struct {
	Clients int
	Error   error
}

type ClntDataReply struct {
	Client
	Error error
}

type ScriptReply struct {
	Script []string
	Error  error
}

type BinaryReply struct {
	Binary []byte
	Error  error
}

type BootReq struct {
	Images []string
}

type BootReply struct {
	Reply      int
	ImageName  string
	Script     string
	ScriptType string
	Binary     []byte
	Error      error
}

var ClientCfg map[string]*Client
var ClientBootCfg map[string]*BootcConfig
var regReq RegReq
var regReply RegReply

func bootText(i int) string {
	var bootStates = []string{
		"Not-Registered",
		"Registered",
		"Booting",
		"Up",
		"Installing",
		"Rebooting",
	}
	return bootStates[i]
}

func installText(i int) string {
	var installStates = []string{
		"Factory",
		"Installing",
		"Installed",
		"Install failed",
		"Restoring",
		"Restore failed",
	}
	return installStates[i]
}

func distroText(i int) string {
	var distroTypes = []string{
		"Debian",
	}
	return distroTypes[i]
}

func scriptText(i int) string {
	var scripts = []string{
		"Boot-latest",
		"Boot-known-good",
		"Debian-install",
	}
	return scripts[i]
}
