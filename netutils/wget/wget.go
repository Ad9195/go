package wget

import (
	"fmt"

	"github.com/cavaliercoder/grab"
	"github.com/platinasystems/go/url"
)

const Name = "wget"

type cmd struct{}

func New() cmd { return cmd{} }

func (cmd) String() string { return Name }
func (cmd) Usage() string  { return Name + ` URL...` }

func (cmd) Main(args ...string) error {
	// validate command args
	if len(args) < 1 {
		return fmt.Errorf("URL: missing")
	}

	reqs := make([]*grab.Request, 0)
	for _, url := range args {
		req, err := grab.NewRequest(url)
		if err != nil {
			return err
		}
		reqs = append(reqs, req)
	}

	successes, err := url.FetchReqs(0, reqs)
	if successes == 0 && err != nil {
		return err
	}

	fmt.Printf("%d files successfully downloaded.\n", successes)
	return nil
}
