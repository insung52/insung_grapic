# Static Analysis Review: A-15 (KTX2 Buffer Range Verification)

We have reviewed the fix applied for the **A-15** static analysis issue in [ktx2_reader.cc](file:///C:/working/grapi-base/base/src/grapi/base/providers/ktx2_reader.cc). 

Below is an analysis of what is correctly handled, a **critical security vulnerability** that remains in the current implementation, and the proposed code change to address it.

---

## 1. Correctly Handled: Offset and Length Range Checks

The range checks added to prevent out-of-bounds (OOB) reads during `memcpy` of level data are **correctly implemented**.

```cpp
// Check in Ktx2Reader::load() & FAsync::doTranscoding()
if (offset > size || length > size - offset) {
  // Safe error handling
}
```

### Why it is correct:
1. **Prevents Integer Overflow**: Using `length > size - offset` instead of `offset + length > size` is the industry standard for range checks. Since `offset <= size` is verified first, `size - offset` is guaranteed not to underflow, preventing integer wrapping attacks.
2. **Prevents OOB Read**: It ensures that reading `length` bytes starting at `data + offset` is completely within the bounds of the original buffer, preventing potential information disclosure or segmentation faults during `memcpy`.

---

## 2. Critical Security Finding: Heap OOB Write in `FAsync::doTranscoding`

A critical vulnerability still exists in the fallback asynchronous path (uncompressed/untranscoded path, i.e., when BasisU transcoder initialization fails and `second == 1`).

### Vulnerability Flow:
1. An attacker provides a KTX2 file with `header->level_count = 17` (or any value larger than `KTX2_MAX_SUPPORTED_LEVEL_COUNT` which is `16`).
2. `Ktx2Reader::asyncCreate()` is called. It initializes `ktx2_transcoder`, but initialization fails because the BasisU library internally rejects files with more than 16 levels.
3. Because transcoder initialization failed, the code falls back to:
   ```cpp
   Texture* texture = createTexture(data, size);
   second = 1;
   ```
4. `createTexture(data, size)` reads `header->level_count` (17) and builds a texture with 17 mip-levels. Since there is no upper-bound validation on `level_count` in this function, it successfully returns the texture.
5. Back in `asyncCreate()`, since `second == 1`, the transcoder is deleted and a new `FAsync` object is created:
   ```cpp
   return new FAsync(texture, engine_, nullptr, std::move(ktx2content));
   ```
6. On the background thread, `FAsync::doTranscoding()` is called. Since `transcoder_` is `nullptr`, it goes to the `else` branch:
   ```cpp
   for (vuint32 level = 0; level < header->level_count; ++level) {
     // ...
     transcoder_results_[level].store(pbd); // <-- CRITICAL BUG!
   }
   ```
7. Since `transcoder_results_` is statically allocated in `FAsync` with size `KTX2_MAX_SUPPORTED_LEVEL_COUNT` (16):
   ```cpp
   TranscoderResult transcoder_results_[KTX2_MAX_SUPPORTED_LEVEL_COUNT] = {};
   ```
   Writing to `transcoder_results_[16]` causes a **Heap Buffer Overflow / Out-of-Bounds Write**.

### Impact:
This OOB write corrupts the member variables located after `transcoder_results_` in the `FAsync` class, including `texture_`, `engine_`, and `source_buffer_` pointers. This can lead to a crash, memory leaks, or potentially arbitrary code execution.

---

## 3. Proposed Fix

To completely resolve the A-15 issue and make it secure, we must validate `header->level_count` inside `createTexture(const void* data, vsize size)`. 

### Recommended Code Change

Add the level count validation in [ktx2_reader.cc](file:///C:/working/grapi-base/base/src/grapi/base/providers/ktx2_reader.cc#L842-L845) right after parsing the header:

```diff
  // 헤더 읽기
  const Ktx2Header* header = reinterpret_cast<const Ktx2Header*>(data);  // NOLINT(cppcoreguidelines-pro-type-reinterpret-cast)
 
+ // 레벨 수 검증 (0이거나 최대 지원 개수를 초과하는 경우 방지)
+ if (header->level_count == 0 || header->level_count > KTX2_MAX_SUPPORTED_LEVEL_COUNT) {
+   return nullptr;
+ }
+
  // 식별자 확인
  if (std::memcmp(header->identifier, kKtx2Identifier.data(), 12) != 0) {  // NOLINT(cppcoreguidelines-pro-bounds-array-to-pointer-decay)
```

### Benefits of this fix:
1. **Enforces implementation limits**: It guarantees that the level count will never exceed `16` in any code path (both synchronous and asynchronous fallback paths).
2. **Prevents integer overflow**: By constraining `header->level_count` to $\le 16$, the calculation of `level_index_size` (`sizeof(Ktx2LevelIndex) * header->level_count`) can never overflow even on 32-bit platforms.
