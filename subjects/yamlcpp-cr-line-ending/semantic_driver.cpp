#include <algorithm>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "yaml-cpp/yaml.h"

static std::string escape_scalar(const std::string& value)
{
    std::ostringstream out;

    for (unsigned char c : value) {
        switch (c) {
            case '\\':
                out << "\\\\";
                break;
            case '\n':
                out << "\\n";
                break;
            case '\r':
                out << "\\r";
                break;
            case '\t':
                out << "\\t";
                break;
            case '"':
                out << "\\\"";
                break;
            default:
                out << static_cast<char>(c);
                break;
        }
    }

    return out.str();
}

static std::string canonical(const YAML::Node& node)
{
    if (!node.IsDefined()) {
        return "UNDEFINED";
    }

    if (node.IsNull()) {
        return "NULL";
    }

    if (node.IsScalar()) {
        return "SCALAR(\"" + escape_scalar(node.Scalar()) + "\")";
    }

    if (node.IsSequence()) {
        std::ostringstream out;
        out << "SEQ[";

        for (std::size_t i = 0; i < node.size(); ++i) {
            if (i != 0) {
                out << ",";
            }

            out << canonical(node[i]);
        }

        out << "]";
        return out.str();
    }

    if (node.IsMap()) {
        std::vector<std::string> entries;

        for (auto it = node.begin(); it != node.end(); ++it) {
            entries.push_back(
                canonical(it->first)
                + "=>"
                + canonical(it->second)
            );
        }

        std::sort(entries.begin(), entries.end());

        std::ostringstream out;
        out << "MAP{";

        for (std::size_t i = 0; i < entries.size(); ++i) {
            if (i != 0) {
                out << ",";
            }

            out << entries[i];
        }

        out << "}";
        return out.str();
    }

    return "UNKNOWN";
}

int main(int argc, char** argv)
{
    if (argc != 2) {
        std::cerr << "usage: " << argv[0] << " input.yaml\n";
        return 64;
    }

    try {
        YAML::Node node = YAML::LoadFile(argv[1]);

        std::cout
            << "TREE="
            << canonical(node)
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
