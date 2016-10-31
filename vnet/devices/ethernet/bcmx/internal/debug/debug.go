// +build debug

package debug

import (
	"fmt"
)

func CheckRegAddr(name string, got, want uint) {
	if got != want {
		panic(fmt.Errorf("%s got 0x%x != want 0x%x", name, got, want))
	}
}
