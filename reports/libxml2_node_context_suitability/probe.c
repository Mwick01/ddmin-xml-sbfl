#include <stdio.h>
#include <string.h>

#include <libxml/HTMLparser.h>
#include <libxml/parser.h>
#include <libxml/tree.h>

int main(int argc, char **argv) {
    static const char html[] =
        "<html><body><div>context</div></body></html>";

    const char *fragment =
        argc > 1
        ? argv[1]
        : "<span>probe</span>";

    xmlDocPtr doc = NULL;
    xmlNodePtr root = NULL;
    xmlNodePtr list = NULL;
    xmlNsPtr ns = NULL;
    xmlParserErrors result;

    doc = htmlReadMemory(
        html,
        (int)strlen(html),
        NULL,
        NULL,
        HTML_PARSE_NOERROR |
        HTML_PARSE_NOWARNING
    );

    if (doc == NULL) {
        fprintf(stderr, "htmlReadMemory failed\n");
        return 2;
    }

    root = xmlDocGetRootElement(doc);

    if (root == NULL) {
        fprintf(stderr, "no root\n");
        xmlFreeDoc(doc);
        return 2;
    }

    /*
     * Reproduce the upstream condition:
     * an HTML document with a namespace added manually.
     */
    ns = xmlNewNs(
        root,
        BAD_CAST "urn:probe",
        BAD_CAST "p"
    );

    if (ns == NULL) {
        fprintf(stderr, "xmlNewNs failed\n");
        xmlFreeDoc(doc);
        return 2;
    }

    result = xmlParseInNodeContext(
        root,
        fragment,
        (int)strlen(fragment),
        0,
        &list
    );

    printf(
        "result=%d list=%s\n",
        (int)result,
        list != NULL ? "non-null" : "null"
    );

    xmlFreeNodeList(list);
    xmlFreeDoc(doc);
    xmlCleanupParser();

    return 0;
}
