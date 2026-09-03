<?php
defined('_JEXEC') or die;

class plgAjaxJpcconnector extends JPlugin
{
    protected $autoloadLanguage = true;
    const PROTOCOL_VERSION = 1;
    const CONNECTOR_VERSION = '1.0.0';
    const MAX_BODY_BYTES = 2097152;

    public function onAjaxJpcconnector()
    {
        try {
            $this->checkAllowedIp();
            $this->authenticate();
            $request = $this->readRequest();
            $protocol = isset($request['protocol']) ? (int) $request['protocol'] : 0;

            if ($protocol !== self::PROTOCOL_VERSION) {
                throw new RuntimeException('Unsupported connector protocol', 400);
            }

            $action = isset($request['action']) ? (string) $request['action'] : '';

            switch ($action) {
                case 'ping':
                    $this->respond(array(
                        'connector_version' => self::CONNECTOR_VERSION,
                        'joomla_version' => JVERSION,
                    ));
                    break;

                case 'get':
                    $this->respond($this->getArticle($request));
                    break;

                case 'create':
                    $this->respond($this->createArticle($request), 201);
                    break;

                case 'adopt':
                    $this->respond($this->writeArticle($request, true));
                    break;

                case 'update':
                    $this->respond($this->writeArticle($request, false));
                    break;

                default:
                    throw new RuntimeException('Unknown connector action', 400);
            }
        } catch (RuntimeException $exception) {
            $status = (int) $exception->getCode();
            if ($status < 400 || $status > 599) {
                $status = 500;
            }
            $this->respondError($exception->getMessage(), $status);
        } catch (Exception $exception) {
            $this->respondError('Internal connector error', 500);
        }

        return null;
    }

    private function readRequest()
    {
        $raw = file_get_contents('php://input');

        if (!is_string($raw) || $raw === '') {
            throw new RuntimeException('Empty JSON request', 400);
        }
        if (strlen($raw) > self::MAX_BODY_BYTES) {
            throw new RuntimeException('Request body is too large', 413);
        }

        $payload = json_decode($raw, true);
        if (!is_array($payload)) {
            throw new RuntimeException('Invalid JSON request', 400);
        }

        return $payload;
    }

    private function authenticate()
    {
        $stored = trim((string) $this->params->get('token', ''));
        $provided = isset($_SERVER['HTTP_X_JPC_TOKEN'])
            ? trim((string) $_SERVER['HTTP_X_JPC_TOKEN'])
            : '';

        if (strlen($stored) < 32 || strlen($provided) < 32) {
            throw new RuntimeException('Invalid connector token', 401);
        }

        $isHash = preg_match('/^\$2[axy]\$/', $stored) === 1;
        if ($isHash) {
            $valid = JUserHelper::verifyPassword($provided, $stored);
        } else {
            $valid = $this->safeEquals($stored, $provided);
        }

        if (!$valid) {
            throw new RuntimeException('Invalid connector token', 401);
        }

        if (!$isHash) {
            $this->replaceStoredTokenWithHash($provided);
        }
    }

    private function safeEquals($known, $provided)
    {
        if (function_exists('hash_equals')) {
            return hash_equals($known, $provided);
        }

        if (strlen($known) !== strlen($provided)) {
            return false;
        }

        $difference = 0;
        for ($index = 0; $index < strlen($known); $index++) {
            $difference |= ord($known[$index]) ^ ord($provided[$index]);
        }

        return $difference === 0;
    }

    private function replaceStoredTokenWithHash($token)
    {
        $db = JFactory::getDbo();
        $query = $db->getQuery(true)
            ->select($db->quoteName(array('extension_id', 'params')))
            ->from($db->quoteName('#__extensions'))
            ->where($db->quoteName('type') . ' = ' . $db->quote('plugin'))
            ->where($db->quoteName('folder') . ' = ' . $db->quote('ajax'))
            ->where($db->quoteName('element') . ' = ' . $db->quote('jpcconnector'));
        $db->setQuery($query);
        $extension = $db->loadObject();

        if (!$extension) {
            return;
        }

        $params = new JRegistry;
        $params->loadString((string) $extension->params);
        $params->set('token', JUserHelper::hashPassword($token));
        $extension->params = (string) $params;

        try {
            $db->updateObject('#__extensions', $extension, 'extension_id');
        } catch (Exception $exception) {
            // Authentication succeeded; a later request can retry migration.
        }
    }

    private function checkAllowedIp()
    {
        $configured = trim((string) $this->params->get('allowed_ip', ''));
        if ($configured === '') {
            return;
        }

        $allowed = preg_split('/[\s,;]+/', $configured, -1, PREG_SPLIT_NO_EMPTY);
        $remote = isset($_SERVER['REMOTE_ADDR']) ? (string) $_SERVER['REMOTE_ADDR'] : '';

        if (!in_array($remote, $allowed, true)) {
            throw new RuntimeException('Source IP is not allowed', 403);
        }
    }

    private function contentTable()
    {
        JTable::addIncludePath(
            JPATH_ADMINISTRATOR . '/components/com_content/tables'
        );
        $table = JTable::getInstance('Content');

        if (!$table) {
            throw new RuntimeException('Joomla content table is unavailable', 500);
        }

        return $table;
    }

    private function loadArticle($articleId)
    {
        $articleId = (int) $articleId;
        if ($articleId < 1) {
            throw new RuntimeException('Invalid article ID', 400);
        }

        $table = $this->contentTable();
        if (!$table->load($articleId)) {
            throw new RuntimeException('Article not found', 404);
        }

        return $table;
    }

    private function articleBody($table)
    {
        $intro = (string) $table->introtext;
        $full = (string) $table->fulltext;

        if ($full === '') {
            return $intro;
        }

        return $intro . '<hr id="system-readmore" />' . $full;
    }

    private function articleData($table)
    {
        return array(
            'id' => (int) $table->id,
            'title' => (string) $table->title,
            'alias' => (string) $table->alias,
            'body_html' => $this->articleBody($table),
        );
    }

    private function getArticle($request)
    {
        $articleId = isset($request['article_id']) ? $request['article_id'] : 0;
        return $this->articleData($this->loadArticle($articleId));
    }

    private function markerHtml($request)
    {
        $uuid = isset($request['marker_uuid'])
            ? strtolower(trim((string) $request['marker_uuid']))
            : '';

        if (!preg_match(
            '/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/',
            $uuid
        )) {
            throw new RuntimeException('Invalid managed marker UUID', 400);
        }

        return '<!-- JPC-MANAGED-PAGE:' . $uuid . ' -->';
    }

    private function assertExpectedHash($body, $request)
    {
        $expected = isset($request['expected_hash'])
            ? strtolower((string) $request['expected_hash'])
            : '';

        if (!preg_match('/^[0-9a-f]{64}$/', $expected)) {
            throw new RuntimeException('Invalid expected article hash', 400);
        }
        if (!$this->safeEquals(hash('sha256', $body), $expected)) {
            throw new RuntimeException(
                'Article changed after JPC read it; reload before writing',
                409
            );
        }
    }

    private function splitArticleBody($html)
    {
        $parts = preg_split(
            '/<hr\b(?=[^>]*\bid\s*=\s*["\']system-readmore["\'])[^>]*>/i',
            $html,
            2
        );

        return array(
            isset($parts[0]) ? $parts[0] : '',
            isset($parts[1]) ? $parts[1] : '',
        );
    }

    private function createArticle($request)
    {
        $title = isset($request['title']) ? trim((string) $request['title']) : '';
        $alias = isset($request['alias']) ? trim((string) $request['alias']) : '';
        $categoryId = isset($request['category_id'])
            ? (int) $request['category_id']
            : 0;
        $html = isset($request['html']) ? (string) $request['html'] : '';
        $marker = $this->markerHtml($request);

        if ($title === '' || $categoryId < 1) {
            throw new RuntimeException(
                'Article title and category ID are required',
                400
            );
        }
        if (strpos($html, $marker) === false) {
            throw new RuntimeException(
                'Managed marker is missing from new article',
                409
            );
        }

        if ($alias === '') {
            $alias = JApplicationHelper::stringURLSafe($title);
        }
        if ($alias === '') {
            $alias = JFactory::getDate()->format('Y-m-d-H-i-s');
        }

        list($introtext, $fulltext) = $this->splitArticleBody($html);
        $table = $this->contentTable();
        $now = JFactory::getDate()->toSql();
        $data = array(
            'id' => 0,
            'title' => $title,
            'alias' => $alias,
            'catid' => $categoryId,
            'introtext' => $introtext,
            'fulltext' => $fulltext,
            'state' => 1,
            'access' => 1,
            'language' => '*',
            'created' => $now,
            'created_by' => 0,
            'publish_up' => $now,
            'metadata' => '{}',
            'attribs' => '{}',
            'images' => '{}',
            'urls' => '{}',
        );

        if (!$table->bind($data) || !$table->check() || !$table->store()) {
            $error = $table->getError();
            throw new RuntimeException(
                $error ? $error : 'Joomla rejected article creation',
                500
            );
        }

        return $this->articleData($table);
    }

    private function writeArticle($request, $adoption)
    {
        $articleId = isset($request['article_id']) ? $request['article_id'] : 0;
        $html = isset($request['html']) ? (string) $request['html'] : '';
        $marker = $this->markerHtml($request);
        $table = $this->loadArticle($articleId);
        $current = $this->articleBody($table);

        $this->assertExpectedHash($current, $request);

        if ($adoption) {
            if (strpos($current, '<!-- JPC-MANAGED-PAGE:') !== false) {
                throw new RuntimeException(
                    'Article already contains a JPC managed marker',
                    409
                );
            }
        } elseif (strpos($current, $marker) === false) {
            throw new RuntimeException(
                'Current article managed marker does not match',
                409
            );
        }

        if (strpos($html, $marker) === false) {
            throw new RuntimeException(
                'Managed marker is missing from replacement HTML',
                409
            );
        }

        if (!empty($table->checked_out)) {
            $table->checkin((int) $table->id);
            $table = $this->loadArticle($articleId);
        }

        list($introtext, $fulltext) = $this->splitArticleBody($html);
        $table->introtext = $introtext;
        $table->fulltext = $fulltext;
        $table->modified = JFactory::getDate()->toSql();
        $table->modified_by = 0;
        $table->version = (int) $table->version + 1;

        if (!$table->check() || !$table->store(true)) {
            $error = $table->getError();
            throw new RuntimeException(
                $error ? $error : 'Joomla rejected article update',
                500
            );
        }

        return $this->articleData($table);
    }

    private function respond($data, $status = 200)
    {
        $app = JFactory::getApplication();
        http_response_code((int) $status);
        $app->setHeader('Content-Type', 'application/json; charset=utf-8', true);
        $app->setHeader('Cache-Control', 'no-store', true);
        echo json_encode(array(
            'ok' => true,
            'data' => $data,
        ));
        $app->close();
    }

    private function respondError($message, $status)
    {
        $app = JFactory::getApplication();
        http_response_code((int) $status);
        $app->setHeader('Content-Type', 'application/json; charset=utf-8', true);
        $app->setHeader('Cache-Control', 'no-store', true);
        echo json_encode(array(
            'ok' => false,
            'error' => (string) $message,
        ));
        $app->close();
    }
}
