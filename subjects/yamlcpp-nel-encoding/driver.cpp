#include <iomanip>
#include <iostream>
#include <string>

#include "yaml-cpp/yaml.h"

int main(int argc, char** argv)
{
    if (argc != 2) {
        std::cerr << "usage: "
                  << argv[0]
                  << " input.yaml\n";
        return 64;
    }

    try {
        YAML::Node doc =
            YAML::LoadFile(argv[1]);

        if (!doc["value"]) {
            std::cerr << "VALUE_MISSING\n";
            return 3;
        }

        const std::string value =
            doc["value"].as<std::string>();

        std::cout
            << "SIZE="
            << value.size()
            << "\n";

        std::cout << "HEX=";

        for (unsigned char c : value) {
            std::cout
                << std::uppercase
                << std::hex
                << std::setw(2)
                << std::setfill('0')
                << static_cast<unsigned int>(c);
        }

        std::cout << "\n";

        return 0;
    }
    catch (const YAML::Exception& e) {
        std::cerr
            << "YAML_ERROR: "
            << e.what()
            << "\n";
        return 2;
    }
}
