#include <iostream>
#include "tinyxml2.h"

int main(int argc, char** argv)
{
    if (argc != 2)
    {
        std::cerr << "usage: " << argv[0] << " input.xml\n";
        return 64;
    }

    tinyxml2::XMLDocument doc;

    tinyxml2::XMLError result = doc.LoadFile(argv[1]);

    if (result == tinyxml2::XML_SUCCESS)
    {
        std::cout << "PARSE_OK\n";
        return 0;
    }

    std::cout
        << "PARSE_ERROR code=" << static_cast<int>(result)
        << " name=\"" << doc.ErrorName() << "\"\n";

    return 2;
}
