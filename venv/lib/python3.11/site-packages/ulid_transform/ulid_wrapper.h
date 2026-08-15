#include <string>

#ifndef ULID_WRAPPER_H
#define ULID_WRAPPER_H

std::string _cpp_ulid();
std::string _cpp_ulid_at_time(double timestamp);
std::string _cpp_ulid_to_bytes(const char * ulid_string);
std::string _cpp_bytes_to_ulid(std::string bytes_string);

#endif
