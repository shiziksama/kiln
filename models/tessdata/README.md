# Tesseract display model

`display.traineddata` is the upstream `7seg.traineddata`, renamed so the
application invokes `tesseract -l display --tessdata-dir models/tessdata`.
It is a trained LSTM font model used by Tesseract, not a hand-coded segment
classifier. No executable code from the model repository is run.

Source: https://github.com/Shreeshrii/tessdata_ssd
Download: https://raw.githubusercontent.com/Shreeshrii/tessdata_ssd/master/7seg.traineddata
Retrieved: 2026-10-20
SHA-256: 7e170293e5ac660295d7d3f53346453447bd9c9845f9f384cc1005c791487291
License: Apache-2.0, reproduced in LICENSE.

The general English model dropped the final 5 in real 025 images. This model
reads both 025 and 026, and is checked against synthetic examples of all ten
digit shapes. Real camera coverage is currently limited to the temperatures
observed during testing; synthetic checks do not establish real-world accuracy
at all temperatures or lighting conditions.
