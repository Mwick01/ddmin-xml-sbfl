// Coverage-only driver: retain the original assertion and flush on SIGABRT.
// Used only for this single-threaded exploratory TinyXML-2 #997 experiment.
#include <csignal>
#include <cstdlib>
#include <iostream>
#include "tinyxml2.h"

extern "C" void __gcov_dump(void);

static void flush_coverage_on_abort(int)
{
    __gcov_dump();
    std::_Exit(134);
}

int main(int argc, char** argv)
{
    std::signal(SIGABRT, flush_coverage_on_abort);
    if (argc != 2) {
        std::cerr << "usage: " << argv[0] << " input.xml\n";
        return 64;
    }

    tinyxml2::XMLDocument doc;
    tinyxml2::XMLError result = doc.LoadFile(argv[1]);
    if (result == tinyxml2::XML_SUCCESS) {
        std::cout << "PARSE_OK\n";
        return 0;
    }
    std::cout << "PARSE_ERROR code=" << static_cast<int>(result)
              << " name=\"" << doc.ErrorName() << "\"\n";
    return 2;
}
