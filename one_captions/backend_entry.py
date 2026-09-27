"""One frozen executable serves setup, backend and workers."""
import sys
if len(sys.argv)>1 and sys.argv[1]=='--setup':
 from one_captions.setup_models import setup
 setup(sys.argv[2])
elif len(sys.argv)>1 and sys.argv[1]=='--worker':
 sys.argv.pop(1)
 from one_captions import worker
else:
 from one_captions import server
 server.main()
