#include "ulid_wrapper.h"
#include "ulid.hh"

using namespace std;

std::string _cpp_ulid() {
  ulid::ULID ulid;
  ulid::EncodeTimeSystemClockNow(ulid);
  ulid::EncodeEntropyRand(ulid);
  return ulid::Marshal(ulid);
}

std::string _cpp_ulid_at_time(double epoch_time) {
  ulid::ULID ulid;
  ulid::EncodeTimestamp(static_cast<int64_t>(epoch_time*1000), ulid);
  ulid::EncodeEntropyRand(ulid);
  return ulid::Marshal(ulid);
}

std::string _cpp_ulid_to_bytes(const char * ulid_string) {
  ulid::ULID ulid;
  ulid::UnmarshalFrom(ulid_string, ulid);
  std::vector<uint8_t> data = ulid::MarshalBinary(ulid);
  std::string str(reinterpret_cast<char *>(data.data()), data.size());
  return str;
}

std::string _cpp_bytes_to_ulid(std::string bytes_string) {
  std::vector<uint8_t> data(bytes_string.begin(), bytes_string.end());
  ulid::ULID ulid = ulid::UnmarshalBinary(data);
  return ulid::Marshal(ulid);
}
