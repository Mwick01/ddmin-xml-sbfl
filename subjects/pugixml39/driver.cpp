#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

#include "pugixml.hpp"

int main(int argc, char** argv)
{
    if (argc != 2)
    {
        std::cerr << "usage: " << argv[0] << " input.xml\n";
        return 64;
    }

    std::ifstream in(argv[1], std::ios::binary);

    if (!in)
    {
        std::cerr << "cannot open input\n";
        return 65;
    }

    std::vector<char> data(
        (std::istreambuf_iterator<char>(in)),
        std::istreambuf_iterator<char>()
    );

    pugi::xml_document doc;
    pugi::xml_parse_result result =
        doc.load_buffer(data.data(), data.size());

    if (result)
    {
        std::cout << "PARSE_OK\n";
        return 0;
    }

    std::cout
        << "PARSE_ERROR status=" << result.status
        << " offset=" << result.offset
        << " description=\"" << result.description() << "\"\n";

    return 2;
}
