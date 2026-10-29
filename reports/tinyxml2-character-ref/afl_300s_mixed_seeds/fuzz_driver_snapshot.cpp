// Exploratory AFL driver: keep assertion paths available for mutation.
// Outcomes are independently classified using the original buggy/fixed binaries.
#include <csignal>
#include <cstdlib>
#include <iostream>
#include "tinyxml2.h"

static void exit_on_abort(int)
{
    std::_Exit(134);
}

int main(int argc, char** argv)
{
    std::signal(SIGABRT, exit_on_abort);
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
