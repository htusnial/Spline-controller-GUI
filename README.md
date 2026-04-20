# MetaMobility Unified GUI

Exoskeleton control interface that wraps both the Spline Controller
and the Biotorque Controller behind a home screen with seamless
mode-switching.



## Running

```bash
cd MetaMobility_Unified
python main_gui.py
```

## Dependencies

PyQt5
pyqtgraph
numpy
scipy

Install with:

```bash
pip install PyQt5 pyqtgraph numpy scipy
```

## Notes

* Controller script paths are still hardcoded per the originals.
  Update `_start_controller()` in `spline_panel.py` and `_write_temp_config()`
  in `biotorque_panel.py` if the scripts live elsewhere.
* Both panels share **UDP port 47269** for data reception.
  Only one panel should be open / listening at a time.
