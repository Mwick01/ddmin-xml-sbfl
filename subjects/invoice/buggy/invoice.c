#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <libxml/parser.h>
#include <libxml/tree.h>

/*
 * Convert an XML attribute into an integer safely.
 *
 * Returns:
 *   0  - conversion succeeded
 *  -1  - missing or invalid integer
 */
static int parse_integer_attribute(
    xmlNodePtr node,
    const char *attribute_name,
    int *result
) {
    xmlChar *attribute_value =
        xmlGetProp(node, BAD_CAST attribute_name);

    if (attribute_value == NULL) {
        fprintf(
            stderr,
            "Missing attribute '%s'.\n",
            attribute_name
        );
        return -1;
    }

    char *end_pointer = NULL;
    errno = 0;

    long parsed_value = strtol(
        (const char *)attribute_value,
        &end_pointer,
        10
    );

    if (
        errno != 0 ||
        end_pointer == (char *)attribute_value ||
        *end_pointer != '\0' ||
        parsed_value < 0 ||
        parsed_value > INT_MAX
    ) {
        fprintf(
            stderr,
            "Invalid value for attribute '%s': %s\n",
            attribute_name,
            (const char *)attribute_value
        );

        xmlFree(attribute_value);
        return -1;
    }

    *result = (int)parsed_value;

    xmlFree(attribute_value);
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <xml-file>\n", argv[0]);
        return 2;
    }

    const char *xml_filename = argv[1];

    /*
     * XML_PARSE_NONET prevents the parser from accessing network resources.
     */
    xmlDocPtr document = xmlReadFile(
        xml_filename,
        NULL,
        XML_PARSE_NONET
    );

    if (document == NULL) {
        fprintf(stderr, "Could not parse XML file.\n");
        return 1;
    }

    xmlNodePtr root = xmlDocGetRootElement(document);

    if (
        root == NULL ||
        root->type != XML_ELEMENT_NODE ||
        xmlStrcmp(root->name, BAD_CAST "invoice") != 0
    ) {
        fprintf(stderr, "Root element must be <invoice>.\n");
        xmlFreeDoc(document);
        return 3;
    }

    long long total = 0;

    for (
        xmlNodePtr node = root->children;
        node != NULL;
        node = node->next
    ) {
        /*
         * Ignore whitespace and text nodes between XML elements.
         */
        if (node->type != XML_ELEMENT_NODE) {
            continue;
        }

        if (xmlStrcmp(node->name, BAD_CAST "item") != 0) {
            continue;
        }

        xmlChar *type_value =
            xmlGetProp(node, BAD_CAST "type");

        if (type_value == NULL) {
            fprintf(stderr, "Item is missing the 'type' attribute.\n");
            xmlFreeDoc(document);
            return 3;
        }

        int price = 0;
        int quantity = 0;

        if (
            parse_integer_attribute(node, "price", &price) != 0 ||
            parse_integer_attribute(node, "quantity", &quantity) != 0
        ) {
            xmlFree(type_value);
            xmlFreeDoc(document);
            return 3;
        }

        /*
         *  calculation.
         */
        if (xmlStrcmp(type_value, BAD_CAST "special") == 0) {
            total += price + quantity; /* Intentional fault */
        } else {
            total += (long long)price * quantity;
        }

        xmlFree(type_value);
    }

    printf("TOTAL=%lld\n", total);

    xmlFreeDoc(document);
    xmlCleanupParser();

    return 0;
}