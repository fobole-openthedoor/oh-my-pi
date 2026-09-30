---
description: Stop telegraph-style collapse in thinking and replies
condition:
  - '(?m)(?:^[A-Z]{2,24}[.!?]{0,3}\r?\n){8,}'
  - '(?m)(?:^[A-Z]{2,16}\s*[🔥💥✅❌🎯🚀⚠️❗💯✨🎉]?\s*\r?\n){6,}'
  - '(?:[🔥💥✅❌🎯🚀⚠️❗💯✨🎉👍👎]|[\uD83C-\uDBFF][\uDC00-\uDFFF])(?:.{0,16}(?:[🔥💥✅❌🎯🚀⚠️❗💯✨🎉👍👎]|[\uD83C-\uDBFF][\uDC00-\uDFFF])){9,}'
scope: [text, thinking]
interruptMode: always
---

The previous draft collapsed into telegraph style (one word per line, ALL CAPS, or emoji). Continue in normal sentences. No emoji. No all-caps shouting. Keep thinking as prose, then call tools.
