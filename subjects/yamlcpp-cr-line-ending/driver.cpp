#include <iostream>
#include <string>

#include "yaml-cpp/yaml.h"

static void print_escaped(const std::string& value)
{
    for (unsigned char c : value) {
        switch (c) {
            case '\n':
                std::cout << "\\n";
                break;

            case '\r':
                std::cout << "\\r";
                break;

            case '\t':
                std::cout << "\\t";
                break;

            case '\\':
                std::cout << "\\\\";
                break;

            default:
                std::cout << static_cast<char>(c);
                break;
        }
    }
}

int main(int argc, char** argv)
{
    if (argc != 2) {
        std::cerr << "usage: " << argv[0] << " input.yaml\n";
        return 64;
    }

    try {
        YAML::Node node = YAML::LoadFile(argv[1]);

        if (!node["blockText"] || !node["followup"]) {
            std::cerr << "EXPECTED_KEYS_MISSING\n";
            return 3;
        }

        std::string block =
            node["blockText"].as<std::string>();

        int followup =
            node["followup"].as<int>();

        std::cout << "BLOCK=";
        print_escaped(block);
        std::cout << "\n";

        std::cout
            << "FOLLOWUP="
            << followup
            << "\n";

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
